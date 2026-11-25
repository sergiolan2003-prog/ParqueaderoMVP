from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.config import build_operating_day_configuration
from app.core.operating_day import OperatingDayService
from app.modules.accesos.domain.placa import ClasificadorPlaca, PlacaInvalidaError
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
    TarifaNoConfiguradaError,
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
    def __init__(self, db: Session, clock: Clock | None = None) -> None:
        self._db = db
        self._clock = clock or SystemClock()

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
        placa_normalizada = placa.strip().upper()
        carril = self._db.get(Carril, carril_id)
        if carril is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El carril especificado no existe.",
            )
        if carril.sentido != "ENTRADA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El carril seleccionado no corresponde a un punto de entrada.",
            )

        sede = self._db.get(Sede, carril.sede_id)
        if sede is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La sede asociada al carril no existe.",
            )

        try:
            tipo_clasificado = ClasificadorPlaca.clasificar(placa_normalizada)
        except PlacaInvalidaError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error

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
                Pase.vigente_hasta > ocurrido_en,
            )
            .first()
            is not None
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
            try:
                liquidacion = motor.liquidar(
                    sede.id,
                    tipo_vehiculo,
                    ocurrido_en,
                )
            except TarifaNoConfiguradaError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error

        if vehiculo is None:
            self._db.execute(
                postgresql_insert(Vehiculo)
                .values(placa=placa_normalizada, tipo=tipo_vehiculo)
                .on_conflict_do_nothing(index_elements=[Vehiculo.placa])
            )

        self._db.execute(
            postgresql_insert(EventoAcceso)
            .values(
                id=evento_id,
                placa=placa_normalizada,
                carril_id=carril_id,
                ocurrido_en=ocurrido_en,
                confianza_lpr=confianza_lpr,
                lectura_manual=lectura_manual,
                foto_url=foto_url,
            )
            .on_conflict_do_nothing(index_elements=[EventoAcceso.id])
        )

        cobro_creado = False
        cobro_id: UUID | None = None
        tarifa_id: UUID | None = None
        valor: Decimal | None = None
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
