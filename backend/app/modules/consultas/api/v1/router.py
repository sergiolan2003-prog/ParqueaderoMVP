from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.consultas.application.schemas import (
    CobroConsultaResponse,
    EventoConsultaResponse,
    PaginaCobrosResponse,
    PaginaEventosResponse,
)
from app.modules.consultas.application.services import (
    EstadoCobro,
    consultar_cobros,
    consultar_eventos,
    total_paginas,
)

router = APIRouter(
    prefix="/consultas",
    tags=["Consultas"],
    dependencies=[Depends(requiere_rol(Rol.ADMINISTRADOR))],
)
PlacaFilter = Annotated[str | None, Query(max_length=16)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def _validar_rango(desde: date | None, hasta: date | None) -> None:
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La fecha 'desde' no puede ser posterior a 'hasta'.",
        )


@router.get("/eventos", response_model=PaginaEventosResponse)
def consultar_eventos_acceso(
    placa: PlacaFilter = None,
    desde: date | None = None,
    hasta: date | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    db: Session = Depends(get_db),
) -> PaginaEventosResponse:
    _validar_rango(desde, hasta)
    items, total = consultar_eventos(
        db,
        placa=placa,
        desde=desde,
        hasta=hasta,
        page=page,
        page_size=page_size,
    )
    return PaginaEventosResponse(
        items=[EventoConsultaResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_paginas(total, page_size),
    )


@router.get("/cobros", response_model=PaginaCobrosResponse)
def consultar_cobros_parqueadero(
    placa: PlacaFilter = None,
    desde: date | None = None,
    hasta: date | None = None,
    estado: EstadoCobro | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    db: Session = Depends(get_db),
) -> PaginaCobrosResponse:
    _validar_rango(desde, hasta)
    items, total = consultar_cobros(
        db,
        placa=placa,
        desde=desde,
        hasta=hasta,
        estado=estado,
        page=page,
        page_size=page_size,
    )
    return PaginaCobrosResponse(
        items=[CobroConsultaResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_paginas(total, page_size),
    )
