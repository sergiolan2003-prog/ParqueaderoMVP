from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.config import (
    build_operating_day_configuration,
    settings,
)
from app.core.operating_day import OperatingDayService
from app.modules.accesos.domain.exceptions import (
    CarrilNoEncontradoError,
    CarrilNoEsEntradaError,
    EventoAccesoDuplicadoError,
    SedeNoEncontradaError,
)
from app.modules.accesos.domain.lectores import LectorPlaca, LecturaPlaca
from app.modules.accesos.domain.placa import ClasificadorPlaca
from app.modules.accesos.domain.validaciones_ingreso import (
    CadenaValidacionIngreso,
    ContextoValidacionIngreso,
    ValidadorConfianza,
    ValidadorCupo,
    ValidadorPaseVigente,
)
from app.modules.accesos.infrastructure.models import (
    Carril,
    EventoAcceso,
    Sede,
    Vehiculo,
)
from app.modules.cobros.domain.entities import Cobro as CobroEntity
from app.modules.cobros.domain.motor_cobro import (
    EstrategiaCobroConfigurada,
    Liquidacion,
    MotorCobro,
)
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.cobros.infrastructure.repositories import SqlAlchemyCobroRepository
from app.modules.pases.infrastructure.models import Pase
from app.modules.tarifas.infrastructure.repositories import SqlAlchemyTarifaRepository


@dataclass(frozen=True)
class ResultadoEntrada:
    evento_id: UUID
    placa: str
    carril_id: UUID
    ocurrido_en: datetime
    dia_operativo: date
    franja: str
    cobro_creado: bool
    cobro_id: UUID | None
    tarifa_id: UUID | None
    valor: Decimal | None
    pase_vigente: bool


class RegistrarEntradaUseCase:
    def __init__(
        self,
        db: Session,
        clock: Clock | None = None,
        confidence_threshold: float | None = None,
        cadena_validacion: CadenaValidacionIngreso | None = None,
    ) -> None:
        self._db = db
        self._clock = clock or SystemClock()
        self._umbral_confianza = (
            settings.lpr_confidence_threshold
            if confidence_threshold is None
            else confidence_threshold
        )
        self._cadena_validacion = cadena_validacion or CadenaValidacionIngreso(
            (
                ValidadorConfianza(),
                ValidadorCupo(),
                ValidadorPaseVigente(),
            )
        )

    def ejecutar(
        self,
        evento_id: UUID,
        placa: str,
        carril_id: UUID,
        ocurrido_en: datetime,
        confianza_lpr: float = 1.0,
        lectura_manual: bool = False,
        foto_url: str | None = None,
    ) -> ResultadoEntrada:
        return self._ejecutar_lectura(
            evento_id=evento_id,
            lectura=LecturaPlaca(
                placa=placa,
                confianza=confianza_lpr,
                lectura_manual=lectura_manual,
            ),
            carril_id=carril_id,
            ocurrido_en=ocurrido_en,
            foto_url=foto_url,
        )

    def ejecutar_con_lector(
        self,
        evento_id: UUID,
        carril_id: UUID,
        lector: LectorPlaca,
        ocurrido_en: datetime | None = None,
        foto_url: str | None = None,
    ) -> ResultadoEntrada:
        return self._ejecutar_lectura(
            evento_id=evento_id,
            lectura=lector.leer(),
            carril_id=carril_id,
            ocurrido_en=(
                ocurrido_en if ocurrido_en is not None else self._clock.now()
            ),
            foto_url=foto_url,
        )

    def _ejecutar_lectura(
        self,
        evento_id: UUID,
        lectura: LecturaPlaca,
        carril_id: UUID,
        ocurrido_en: datetime,
        foto_url: str | None,
    ) -> ResultadoEntrada:
        placa_normalizada = lectura.placa.strip().upper()
        carril = self._db.get(Carril, carril_id)
        if carril is None:
            raise CarrilNoEncontradoError()
        if carril.sentido != "ENTRADA":
            raise CarrilNoEsEntradaError()

        sede = self._db.get(Sede, carril.sede_id)
        if sede is None:
            raise SedeNoEncontradaError()

        tipo_clasificado = ClasificadorPlaca.clasificar(placa_normalizada)

        vehiculo = self._db.get(Vehiculo, placa_normalizada)
        tipo_vehiculo = vehiculo.tipo if vehiculo is not None else tipo_clasificado

        configuration = replace(
            build_operating_day_configuration(),
            operating_day_start=sede.inicio_dia_operativo,
            timezone=sede.zona_horaria,
        )
        operating_day = OperatingDayService(self._clock, configuration)
        dia_operativo = operating_day.dia_operativo(ocurrido_en)
        franja = operating_day.franja(ocurrido_en)

        pase_vigente = (
            self._db.query(Pase.id)
            .filter(
                Pase.placa == placa_normalizada,
                Pase.sede_id == sede.id,
                Pase.vigente_desde <= ocurrido_en,
                Pase.vigente_hasta >= ocurrido_en,
            )
            .first()
            is not None
        )
        self._cadena_validacion.validar(
            ContextoValidacionIngreso(
                confianza_lpr=lectura.confianza,
                umbral_confianza=self._umbral_confianza,
                lectura_manual=lectura.lectura_manual,
                pase_vigente=pase_vigente,
            )
        )
        cobro_existente = (
            self._db.query(Cobro)
            .filter(
                Cobro.placa == placa_normalizada,
                Cobro.sede_id == sede.id,
                Cobro.dia_operativo == dia_operativo,
            )
            .first()
        )

        liquidacion: Liquidacion | None = None
        if not pase_vigente and cobro_existente is None:
            motor = MotorCobro(
                EstrategiaCobroConfigurada(
                    SqlAlchemyTarifaRepository(self._db),
                    operating_day,
                )
            )
            liquidacion = motor.liquidar(
                sede.id,
                tipo_vehiculo,
                ocurrido_en,
            )

        cobro_creado = False
        cobro_id: UUID | None = None
        tarifa_id: UUID | None = None
        valor: Decimal | None = None

        with self._db.begin_nested():
            if vehiculo is None:
                self._db.execute(
                    postgresql_insert(Vehiculo)
                    .values(placa=placa_normalizada, tipo=tipo_vehiculo)
                    .on_conflict_do_nothing(index_elements=[Vehiculo.placa])
                )

            evento_registrado = self._db.execute(
                postgresql_insert(EventoAcceso)
                .values(
                    id=evento_id,
                    placa=placa_normalizada,
                    carril_id=carril_id,
                    ocurrido_en=ocurrido_en,
                    confianza_lpr=lectura.confianza,
                    lectura_manual=lectura.lectura_manual,
                    foto_url=foto_url,
                )
                .on_conflict_do_nothing(index_elements=[EventoAcceso.id])
                .returning(EventoAcceso.id)
            ).scalar_one_or_none()
            if evento_registrado is None:
                raise EventoAccesoDuplicadoError()

            if cobro_existente is not None:
                cobro_id = cobro_existente.id
                tarifa_id = cobro_existente.tarifa_id
                valor = cobro_existente.valor
            elif not pase_vigente and liquidacion is not None:
                tarifa_id = liquidacion.tarifa.id
                tarifa_valor = liquidacion.tarifa.valor
                valor = tarifa_valor
                if tarifa_valor > Decimal("0.00"):
                    cobro_id = uuid4()
                    cobro_creado = SqlAlchemyCobroRepository(self._db).add(
                        CobroEntity(
                            id=cobro_id,
                            placa=placa_normalizada,
                            sede_id=sede.id,
                            dia_operativo=dia_operativo,
                            tarifa_id=liquidacion.tarifa.id,
                            valor=tarifa_valor,
                            estado="PENDIENTE",
                        )
                    )
                    if not cobro_creado:
                        cobro_existente = (
                            self._db.query(Cobro)
                            .filter(
                                Cobro.placa == placa_normalizada,
                                Cobro.sede_id == sede.id,
                                Cobro.dia_operativo == dia_operativo,
                            )
                            .one()
                        )
                        cobro_id = cobro_existente.id
                        tarifa_id = cobro_existente.tarifa_id
                        valor = cobro_existente.valor

        self._db.commit()
        return ResultadoEntrada(
            evento_id=evento_id,
            placa=placa_normalizada,
            carril_id=carril_id,
            ocurrido_en=ocurrido_en,
            dia_operativo=dia_operativo,
            franja=franja,
            cobro_creado=cobro_creado,
            cobro_id=cobro_id,
            tarifa_id=tarifa_id,
            valor=valor,
            pase_vigente=pase_vigente,
        )
