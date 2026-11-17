from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.modules.accesos.infrastructure.models import EventoAcceso, Vehiculo, Carril
from app.modules.cobros.infrastructure.models import Cobro

class ValidarSalidaVehiculoUseCase:
    def __init__(self, db: Session):
        self.db = db

    def ejecutar(self, placa: str, carril_id: UUID, foto_url: str | None = None) -> dict:
        placa = placa.upper()

        # 1. Verificar que el carril exista y sea de tipo SALIDA
        carril = self.db.query(Carril).filter(Carril.id == carril_id).first()
        if not carril:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El carril especificado no existe."
            )
        if carril.sentido != "SALIDA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El carril seleccionado no corresponde a un punto de salida."
            )

        # 2. Consultar el vehículo
        vehiculo = self.db.query(Vehiculo).filter(Vehiculo.placa == placa).first()
        
        # Una moto o vehículo sin registro previo puede salir
        es_moto = vehiculo and vehiculo.tipo == "MOTO"

        # 3. Verificar si tiene cobros pendientes
        cobro_pendiente = None
        if not es_moto:
            cobro_pendiente = (
                self.db.query(Cobro)
                .filter(Cobro.placa == placa, Cobro.estado == "PENDIENTE")
                .first()
            )

        # 4. Regla de negocio HU-07 (La barrera no abre con deuda)
        barrera_abre = True
        motivo = "Salida autorizada: cobro pagado, sin cobro o pase vigente."

        if cobro_pendiente:
            barrera_abre = False
            motivo = f"F-05: Salida rechazada. El vehículo posee una deuda pendiente (Cobro ID: {cobro_pendiente.id})."

        # 5. Registrar el intento de salida como evento
        nuevo_evento = EventoAcceso(
            id=uuid4(),
            placa=placa,
            carril_id=carril_id,
            ocurrido_en=datetime.utcnow(),
            confianza_lpr=1.0,
            lectura_manual=False,
            foto_url=foto_url
        )
        self.db.add(nuevo_evento)
        self.db.commit()

        return {
            "placa": placa,
            "carril_id": carril_id,
            "barrera_abre": barrera_abre,
            "motivo": motivo,
            "registrado_en": nuevo_evento.ocurrido_en
        }
