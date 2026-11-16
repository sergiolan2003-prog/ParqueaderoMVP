from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.accesos.domain.services import ValidarSalidaVehiculoUseCase

router = APIRouter(prefix="/accesos", tags=["Accesos"])

class SalidaRequest(BaseModel):
    placa: str = Field(..., example="ABC1234")
    carril_id: UUID
    foto_url: str | None = None

class SalidaResponse(BaseModel):
    placa: str
    carril_id: UUID
    barrera_abre: bool
    motivo: str
    registrado_en: str

@router.post("/salida", status_code=status.HTTP_200_OK)
def validar_salida(payload: SalidaRequest, db: Session = Depends(get_db)):
    """
    HU-07 Salida: La barrera no abre con deuda.
    """
    caso_uso = ValidarSalidaVehiculoUseCase(db)
    resultado = caso_uso.ejecutar(
        placa=payload.placa,
        carril_id=payload.carril_id,
        foto_url=payload.foto_url
    )
    return resultado