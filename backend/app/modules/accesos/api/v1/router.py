from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.accesos.application.services import ValidarSalidaVehiculoUseCase
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol

router = APIRouter(prefix="/accesos", tags=["Accesos"])
PLACA_COLOMBIANA_PATTERN = r"^(?:[A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z])$"


class SalidaRequest(BaseModel):
    placa: str = Field(
        ...,
        pattern=PLACA_COLOMBIANA_PATTERN,
        json_schema_extra={"example": "ABC123"},
    )
    carril_id: UUID
    foto_url: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def normalizar_placa(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class SalidaResponse(BaseModel):
    placa: str
    carril_id: UUID
    barrera_abre: bool
    motivo: str
    registrado_en: datetime


@router.post(
    "/salida",
    response_model=SalidaResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def validar_salida(
    payload: SalidaRequest,
    db: Session = Depends(get_db),
) -> SalidaResponse:
    """
    HU-07 Salida: La barrera no abre con deuda.
    """
    caso_uso = ValidarSalidaVehiculoUseCase(db)
    resultado = caso_uso.ejecutar(
        placa=payload.placa, carril_id=payload.carril_id, foto_url=payload.foto_url
    )
    return resultado
