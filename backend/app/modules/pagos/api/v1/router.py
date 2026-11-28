from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.database import get_db
from app.modules.accesos.infrastructure.models import Sede
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.cobros.domain.states import TransicionCobroInvalidaError
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.pagos.application.services import RegistrarPagoEfectivoUseCase
from app.modules.pagos.domain.exceptions import (
    CobroNoEncontradoError,
    CobroYaPagadoError,
    PagoNoPermitidoError,
    PaseNoEncontradoError,
    ReferenciaPagoEnUsoError,
)

router = APIRouter(prefix="/pagos", tags=["Pagos"])


class PagoEfectivoRequest(BaseModel):
    cobro_id: UUID
    referencia_pago: str = Field(min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid")

    @field_validator("referencia_pago", mode="before")
    @classmethod
    def normalizar_referencia(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class PagoEfectivoResponse(BaseModel):
    pago_id: UUID
    cobro_id: UUID
    referencia_pago: str
    valor_pagado: Decimal
    metodo_pago: Literal["EFECTIVO"]
    estado_cobro: str
    pase_id: UUID
    dia_operativo: date
    pagado_en: datetime
    vence_pase_en: datetime


class CobroPendienteResponse(BaseModel):
    cobro_id: UUID
    placa: str
    sede_id: UUID
    sede_nombre: str
    dia_operativo: date
    valor: Decimal


class ErrorResponse(BaseModel):
    detail: str


@router.get(
    "/pendientes",
    response_model=list[CobroPendienteResponse],
    summary="Listar cobros pendientes para el operador",
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def consultar_cobros_pendientes(
    db: Session = Depends(get_db),
) -> list[CobroPendienteResponse]:
    filas = db.execute(
        select(Cobro, Sede.nombre)
        .join(Sede, Cobro.sede_id == Sede.id)
        .where(Cobro.estado == "PENDIENTE")
        .order_by(Cobro.dia_operativo.desc(), Cobro.placa)
    ).all()
    return [
        CobroPendienteResponse(
            cobro_id=cobro.id,
            placa=cobro.placa,
            sede_id=cobro.sede_id,
            sede_nombre=sede_nombre,
            dia_operativo=cobro.dia_operativo,
            valor=cobro.valor,
        )
        for cobro, sede_nombre in filas
    ]


@router.post(
    "/efectivo",
    summary="Registrar un pago en efectivo",
    description=(
        "Paga el valor exacto del cobro pendiente y genera su pase. "
        "Repetir la misma referencia para el mismo cobro devuelve el resultado "
        "original; no se permite usarla para otro cobro."
    ),
    response_model=PagoEfectivoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": PagoEfectivoResponse,
            "description": "Reintento idempotente; devuelve el pago original.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "El cobro no existe.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "El cobro ya fue pagado con otra referencia, está anulado/vencido, "
                "o la referencia ya pertenece a otro cobro."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Solicitud inválida; no se acepta que el cliente "
                "envíe el valor."
            ),
        },
    },
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def registrar_pago_efectivo(
    payload: PagoEfectivoRequest,
    response: Response,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> PagoEfectivoResponse:
    try:
        resultado = RegistrarPagoEfectivoUseCase(db, clock).ejecutar(
            cobro_id=payload.cobro_id,
            referencia_pago=payload.referencia_pago,
        )
    except CobroNoEncontradoError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        CobroYaPagadoError,
        PagoNoPermitidoError,
        PaseNoEncontradoError,
        ReferenciaPagoEnUsoError,
        TransicionCobroInvalidaError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    response.status_code = (
        status.HTTP_200_OK if resultado.repetido else status.HTTP_201_CREATED
    )
    return PagoEfectivoResponse(
        pago_id=resultado.pago_id,
        cobro_id=resultado.cobro_id,
        referencia_pago=resultado.referencia_pago,
        valor_pagado=resultado.valor_pagado,
        metodo_pago="EFECTIVO",
        estado_cobro=resultado.estado_cobro,
        pase_id=resultado.pase_id,
        dia_operativo=resultado.dia_operativo,
        pagado_en=resultado.pagado_en,
        vence_pase_en=resultado.vence_pase_en,
    )
