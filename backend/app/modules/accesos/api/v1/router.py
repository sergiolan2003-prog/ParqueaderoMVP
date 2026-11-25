from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.database import get_db
from app.modules.accesos.application.entry import RegistrarEntradaUseCase
from app.modules.accesos.application.services import ValidarSalidaVehiculoUseCase
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol

router = APIRouter(prefix="/accesos", tags=["Accesos"])
PLACA_COLOMBIANA_PATTERN = r"^(?:[A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z])$"


class EntradaRequest(BaseModel):
    evento_id: UUID
    placa: str = Field(
        ...,
        pattern=PLACA_COLOMBIANA_PATTERN,
        json_schema_extra={"example": "ABC123"},
    )
    carril_id: UUID
    ocurrido_en: datetime
    confianza_lpr: float = Field(default=1.0, ge=0, le=1)
    lectura_manual: bool = False
    foto_url: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def normalizar_placa(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("ocurrido_en")
    @classmethod
    def exigir_instante_con_zona(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ocurrido_en debe incluir zona horaria.")
        return value


class EntradaResponse(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


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
    "/entrada",
    response_model=EntradaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def registrar_entrada(
    payload: EntradaRequest,
    db: Session = Depends(get_db),
) -> EntradaResponse:
    resultado = RegistrarEntradaUseCase(db).ejecutar(
        evento_id=payload.evento_id,
        placa=payload.placa,
        carril_id=payload.carril_id,
        ocurrido_en=payload.ocurrido_en,
        confianza_lpr=payload.confianza_lpr,
        lectura_manual=payload.lectura_manual,
        foto_url=payload.foto_url,
    )
    return EntradaResponse.model_validate(resultado)


@router.post(
    "/salida",
    response_model=SalidaResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def validar_salida(
    payload: SalidaRequest,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> SalidaResponse:
    """
    HU-07 Salida: La barrera no abre con deuda.
    """
    caso_uso = ValidarSalidaVehiculoUseCase(db, clock)
    resultado = caso_uso.ejecutar(
        placa=payload.placa, carril_id=payload.carril_id, foto_url=payload.foto_url
    )
    return resultado
