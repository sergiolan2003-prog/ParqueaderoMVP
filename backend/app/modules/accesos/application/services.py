from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.accesos.infrastructure.models import Carril, EventoAcceso, Vehiculo
from app.modules.cobros.infrastructure.models import Cobro


class ValidarSalidaVehiculoUseCase:
    def __init__(self, db: Session):
        self.db = db

    def ejecutar(
        self,
        placa: str,
        carril_id: UUID,
        foto_url: str | None = None,
    ) -> dict:
        placa = placa.upper()

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

        vehiculo = self.db.query(Vehiculo).filter(Vehiculo.placa == placa).first()
        es_moto = vehiculo and vehiculo.tipo == "MOTO"

        cobro_pendiente = None
        if not es_moto:
            cobro_pendiente = (
                self.db.query(Cobro)
                .filter(Cobro.placa == placa, Cobro.estado == "PENDIENTE")
                .first()
            )

        barrera_abre = True
        motivo = "Salida autorizada: cobro pagado, sin cobro o pase vigente."
        if cobro_pendiente:
            barrera_abre = False
            motivo = (
                "F-05: Salida rechazada. El vehículo posee una deuda "
                f"pendiente (Cobro ID: {cobro_pendiente.id})."
            )

        nuevo_evento = EventoAcceso(
            id=uuid4(),
            placa=placa,
            carril_id=carril_id,
            ocurrido_en=datetime.utcnow(),
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
