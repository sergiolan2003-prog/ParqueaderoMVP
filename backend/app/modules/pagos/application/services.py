from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.config import build_operating_day_configuration
from app.core.operating_day import OperatingDayService
from app.modules.accesos.infrastructure.models import Sede
from app.modules.cobros.domain.states import (
    TransicionCobroInvalidaError,
    estado_cobro,
)
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.pagos.domain.entities import Pago
from app.modules.pagos.domain.exceptions import (
    CobroNoEncontradoError,
    CobroYaPagadoError,
    PagoCobroDuplicadoError,
    PagoDuplicadoError,
    PagoNoPermitidoError,
    PaseNoEncontradoError,
    ReferenciaPagoEnUsoError,
)
from app.modules.pagos.infrastructure.repositories import SqlAlchemyPagoRepository
from app.modules.pases.domain.entities import Pase
from app.modules.pases.infrastructure.repositories import SqlAlchemyPaseRepository


@dataclass(frozen=True)
class ResultadoPagoEfectivo:
    pago_id: UUID
    cobro_id: UUID
    referencia_pago: str
    valor_pagado: Decimal
    metodo_pago: str
    estado_cobro: str
    pase_id: UUID
    dia_operativo: date
    pagado_en: datetime
    vence_pase_en: datetime
    repetido: bool


class RegistrarPagoEfectivoUseCase:
    def __init__(self, db: Session, clock: Clock | None = None) -> None:
        self._db = db
        self._clock = clock or SystemClock()
        self._pagos = SqlAlchemyPagoRepository(db)
        self._pases = SqlAlchemyPaseRepository(db)

    def ejecutar(
        self,
        cobro_id: UUID,
        referencia_pago: str,
    ) -> ResultadoPagoEfectivo:
        referencia = referencia_pago.strip()
        if not referencia:
            raise PagoNoPermitidoError("La referencia de pago es obligatoria.")
        existente = self._pagos.get_by_reference(referencia)
        if existente is not None:
            if existente.cobro_id != cobro_id:
                raise ReferenciaPagoEnUsoError(
                    "La referencia de pago ya pertenece a otro cobro."
                )
            return self._resultado_existente(existente)

        cobro = self._db.scalar(
            select(Cobro)
            .where(Cobro.id == cobro_id)
            .with_for_update()
        )
        if cobro is None:
            raise CobroNoEncontradoError("El cobro solicitado no existe.")

        existente = self._pagos.get_by_reference(referencia)
        if existente is not None:
            if existente.cobro_id != cobro_id:
                raise ReferenciaPagoEnUsoError(
                    "La referencia de pago ya pertenece a otro cobro."
                )
            return self._resultado_existente(existente)

        pago_previo = self._pagos.get_by_charge_id(cobro_id)
        if pago_previo is not None:
            if pago_previo.referencia_pasarela == referencia:
                return self._resultado_existente(pago_previo)
            raise CobroYaPagadoError(
                "El cobro ya tiene un pago registrado con otra referencia."
            )

        try:
            estado_pagado = estado_cobro(cobro.estado).confirmar_pago()
        except TransicionCobroInvalidaError as error:
            raise PagoNoPermitidoError(str(error)) from error

        if cobro.valor <= Decimal("0.00"):
            raise PagoNoPermitidoError(
                "No se puede registrar un pago para un cobro de valor cero."
            )

        sede = self._db.get(Sede, cobro.sede_id)
        if sede is None:
            raise RuntimeError("La sede asociada al cobro no existe.")

        pagado_en = self._clock.now()
        if pagado_en.tzinfo is None or pagado_en.utcoffset() is None:
            raise ValueError("El reloj debe entregar un instante con zona horaria.")
        configuracion = replace(
            build_operating_day_configuration(),
            operating_day_start=sede.inicio_dia_operativo,
            timezone=sede.zona_horaria,
        )
        operating_day = OperatingDayService(self._clock, configuracion)
        dia_operativo = operating_day.dia_operativo(pagado_en)
        vence_pase_en = datetime.combine(
            dia_operativo + timedelta(days=1),
            sede.inicio_dia_operativo,
            tzinfo=configuracion.zone,
        ).astimezone(UTC)
        pago = Pago(
            id=uuid4(),
            cobro_id=cobro.id,
            medio="EFECTIVO",
            valor=cobro.valor,
            referencia_pasarela=referencia,
            pagado_en=pagado_en,
        )
        pase = Pase(
            id=uuid4(),
            cobro_id=cobro.id,
            placa=cobro.placa,
            sede_id=cobro.sede_id,
            dia_operativo=dia_operativo,
            vigente_desde=pagado_en,
            vigente_hasta=vence_pase_en,
        )

        try:
            with self._db.begin_nested():
                self._pagos.add(pago)
                cobro.estado = estado_pagado.codigo
                self._pases.add(pase)
        except PagoDuplicadoError:
            existente = self._pagos.get_by_reference(referencia)
            if existente is None:
                raise
            if existente.cobro_id != cobro_id:
                raise ReferenciaPagoEnUsoError(
                    "La referencia de pago ya pertenece a otro cobro."
                ) from None
            return self._resultado_existente(existente)
        except PagoCobroDuplicadoError:
            existente = self._pagos.get_by_charge_id(cobro_id)
            if existente is None:
                raise
            if existente.referencia_pasarela != referencia:
                raise CobroYaPagadoError(
                    "El cobro ya tiene un pago registrado con otra referencia."
                ) from None
            return self._resultado_existente(existente)

        self._db.commit()
        return ResultadoPagoEfectivo(
            pago_id=pago.id,
            cobro_id=cobro.id,
            referencia_pago=referencia,
            valor_pagado=pago.valor,
            metodo_pago=pago.medio,
            estado_cobro=estado_pagado.codigo,
            pase_id=pase.id,
            dia_operativo=pase.dia_operativo,
            pagado_en=pagado_en,
            vence_pase_en=vence_pase_en,
            repetido=False,
        )

    def _resultado_existente(self, pago: Pago) -> ResultadoPagoEfectivo:
        cobro = self._db.get(Cobro, pago.cobro_id)
        if cobro is None:
            raise CobroNoEncontradoError("El cobro asociado al pago no existe.")
        pase = self._pases.get_by_charge_id(pago.cobro_id)
        if pase is None:
            raise PaseNoEncontradoError(
                "El pago existente no tiene un pase asociado."
            )
        return ResultadoPagoEfectivo(
            pago_id=pago.id,
            cobro_id=pago.cobro_id,
            referencia_pago=pago.referencia_pasarela,
            valor_pagado=pago.valor,
            metodo_pago=pago.medio,
            estado_cobro="PAGADO",
            pase_id=pase.id,
            dia_operativo=pase.dia_operativo,
            pagado_en=pago.pagado_en,
            vence_pase_en=pase.vigente_hasta,
            repetido=True,
        )
