from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.config import build_operating_day_configuration
from app.core.operating_day import OperatingDayService
from app.modules.accesos.infrastructure.models import (
    Carril,
    EventoAcceso,
    Sede,
    Vehiculo,
)
from app.modules.cobros.domain.states import estado_cobro
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.pases.infrastructure.repositories import SqlAlchemyPaseRepository


class ValidarSalidaVehiculoUseCase:
    def __init__(self, db: Session, clock: Clock | None = None):
        self.db = db
        self._clock = clock or SystemClock()

    def ejecutar(
        self,
        placa: str,
        carril_id: UUID,
        foto_url: str | None = None,
    ) -> dict[str, UUID | bool | str | datetime]:
        placa = placa.strip().upper()

        carril = self.db.query(Carril).filter(Carril.id == carril_id).first()
        if not carril:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El carril especificado no existe.",
            )
        if carril.sentido != "SALIDA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El carril seleccionado no corresponde a un punto de salida.",
            )

        sede = self.db.query(Sede).filter(Sede.id == carril.sede_id).first()
        if sede is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La sede asociada al carril no existe.",
            )

        vehiculo = self.db.query(Vehiculo).filter(Vehiculo.placa == placa).first()
        if vehiculo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El vehículo no está registrado.",
            )

        instante = self._clock.now()
        configuracion = replace(
            build_operating_day_configuration(),
            operating_day_start=sede.inicio_dia_operativo,
            timezone=sede.zona_horaria,
        )
        dia_operativo = OperatingDayService(
            clock=self._clock,
            configuration=configuracion,
        ).dia_operativo(instante)

        cobro = None
        if vehiculo.tipo != "MOTO":
            cobro = (
                self.db.query(Cobro)
                .filter(
                    Cobro.placa == placa,
                    Cobro.sede_id == sede.id,
                    Cobro.dia_operativo == dia_operativo,
                )
                .first()
            )
            if cobro is None:
                cobro = (
                    self.db.query(Cobro)
                    .filter(
                        Cobro.placa == placa,
                        Cobro.sede_id == sede.id,
                        Cobro.estado == "PAGADO",
                    )
                    .order_by(Cobro.dia_operativo.desc())
                    .first()
                )

        barrera_abre = True
        motivo = "Salida autorizada: sin cobro o sin deuda vigente."
        if cobro is not None:
            estado = estado_cobro(cobro.estado)
            pase = SqlAlchemyPaseRepository(self.db).get_by_charge_id(cobro.id)
            pase_vigente = pase is not None and pase.esta_vigente(instante)
            barrera_abre = estado.autoriza_salida(pase_vigente)
            if not barrera_abre and cobro.estado == "PENDIENTE":
                motivo = (
                    "F-05: Salida rechazada. El vehículo posee una deuda "
                    f"pendiente (Cobro ID: {cobro.id})."
                )
            elif not barrera_abre and cobro.estado == "PAGADO":
                motivo = (
                    "Salida rechazada: el pase asociado al cobro no está vigente."
                )
            elif not barrera_abre:
                motivo = (
                    f"Salida rechazada: el cobro está en estado {cobro.estado}."
                )
            else:
                motivo = "Salida autorizada mediante un pase vigente."

        nuevo_evento = EventoAcceso(
            id=uuid4(),
            placa=placa,
            carril_id=carril_id,
            ocurrido_en=instante,
            confianza_lpr=1.0,
            lectura_manual=False,
            foto_url=foto_url,
        )
        self.db.add(nuevo_evento)
        self.db.commit()

        return {
            "placa": placa,
            "carril_id": carril_id,
            "barrera_abre": barrera_abre,
            "motivo": motivo,
            "registrado_en": nuevo_evento.ocurrido_en,
        }
