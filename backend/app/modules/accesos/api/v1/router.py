from datetime import date, datetime
from decimal import Decimal
from random import Random
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.config import settings
from app.core.database import get_db
from app.modules.accesos.application.entry import RegistrarEntradaUseCase
from app.modules.accesos.application.services import ValidarSalidaVehiculoUseCase
from app.modules.accesos.domain.exceptions import (
    CarrilNoEncontradoError,
    CarrilNoEsEntradaError,
    ConfianzaLPRInsuficienteError,
    CupoLlenoError,
    EventoAccesoDuplicadoError,
    IngresoRechazadoError,
    SedeNoEncontradaError,
)
from app.modules.accesos.domain.lectores import LectorSimulado
from app.modules.accesos.domain.placa import PlacaInvalidaError
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.cobros.domain.motor_cobro import TarifaNoConfiguradaError

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


class EntradaSimuladaRequest(BaseModel):
    carril_id: UUID = Field(..., description="Carril de entrada donde se registra.")
    evento_id: UUID = Field(
        default_factory=uuid4,
        description="Identificador idempotente del evento.",
    )
    ocurrido_en: datetime | None = Field(
        default=None,
        description="Instante de la lectura; si se omite, usa la hora actual.",
        examples=["2026-03-10T08:00:00-05:00"],
    )
    placa: str | None = Field(
        default=None,
        pattern=PLACA_COLOMBIANA_PATTERN,
        description="Placa opcional para controlar la salida del simulador.",
        examples=["ABC123"],
    )
    confianza_lpr: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Confianza opcional para controlar la salida del simulador.",
        examples=[0.99],
    )
    foto_url: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def normalizar_placa(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("ocurrido_en")
    @classmethod
    def exigir_instante_con_zona(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
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
    lectura_manual: bool

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

def _http_error_ingreso(error: Exception) -> HTTPException:
    if isinstance(error, CupoLlenoError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{error.codigo}: {error.mensaje}",
        )
    if isinstance(error, (CarrilNoEncontradoError, SedeNoEncontradaError)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.mensaje,
        )
    if isinstance(error, CarrilNoEsEntradaError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.mensaje,
        )
    if isinstance(error, EventoAccesoDuplicadoError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{error.codigo}: {error.mensaje}",
        )
    if isinstance(error, TarifaNoConfiguradaError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
    if isinstance(error, PlacaInvalidaError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    if isinstance(error, ConfianzaLPRInsuficienteError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    if isinstance(error, IngresoRechazadoError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    raise error


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
    try:
        resultado = RegistrarEntradaUseCase(
            db,
            confidence_threshold=settings.lpr_confidence_threshold,
        ).ejecutar(
            evento_id=payload.evento_id,
            placa=payload.placa,
            carril_id=payload.carril_id,
            ocurrido_en=payload.ocurrido_en,
            confianza_lpr=payload.confianza_lpr,
            lectura_manual=payload.lectura_manual,
            foto_url=payload.foto_url,
        )
    except (
        CarrilNoEncontradoError,
        CarrilNoEsEntradaError,
        ConfianzaLPRInsuficienteError,
        EventoAccesoDuplicadoError,
        IngresoRechazadoError,
        PlacaInvalidaError,
        SedeNoEncontradaError,
        TarifaNoConfiguradaError,
        CupoLlenoError
    ) as error:
        raise _http_error_ingreso(error) from error
    return EntradaResponse.model_validate(resultado)


@router.post(
    "/entrada/simulada",
    response_model=EntradaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def registrar_entrada_simulada(
    payload: EntradaSimuladaRequest,
    db: Session = Depends(get_db),
) -> EntradaResponse:
    lector = LectorSimulado(
        aleatorio=Random(),
        placa=payload.placa,
        confianza=payload.confianza_lpr,
    )
    try:
        resultado = RegistrarEntradaUseCase(
            db,
            confidence_threshold=settings.lpr_confidence_threshold,
        ).ejecutar_con_lector(
            evento_id=payload.evento_id,
            carril_id=payload.carril_id,
            lector=lector,
            ocurrido_en=payload.ocurrido_en,
            foto_url=payload.foto_url,
        )
    except (
        CarrilNoEncontradoError,
        CarrilNoEsEntradaError,
        ConfianzaLPRInsuficienteError,
        EventoAccesoDuplicadoError,
        IngresoRechazadoError,
        PlacaInvalidaError,
        SedeNoEncontradaError,
        TarifaNoConfiguradaError,
        CupoLlenoError
    ) as error:
        raise _http_error_ingreso(error) from error
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
