from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.accesos.infrastructure.models import Carril, EventoAcceso
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.cobros.api.v1.schemas import (
    CobroAuditoriaItem,
    EventoAuditoriaItem,
    PaginatedResponse,
)
from app.modules.cobros.infrastructure.models import Cobro

router = APIRouter(
    prefix="/api/v1/auditoria",
    tags=["Auditoría"],
    dependencies=[Depends(requiere_rol(Rol.ADMINISTRADOR))],
)


@router.get("/eventos", response_model=PaginatedResponse[EventoAuditoriaItem])
def listar_eventos(
    placa: str | None = Query(default=None, description="Filtrar por placa"),
    sentido: Literal["ENTRADA", "SALIDA"] | None = Query(
        default=None, description="Filtrar por tipo de evento: ENTRADA o SALIDA"
    ),
    lectura_manual: bool | None = Query(
        default=None, description="Filtrar por eventos de lectura manual"
    ),
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EventoAuditoriaItem]:
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Rango de fechas inválido: "
                "fecha_desde no puede ser mayor que fecha_hasta."
            ),
        )

    query = db.query(EventoAcceso, Carril.sentido).join(
        Carril, EventoAcceso.carril_id == Carril.id
    )

    if placa:
        query = query.filter(EventoAcceso.placa == placa.strip().upper())
    if sentido:
        query = query.filter(Carril.sentido == sentido)
    if lectura_manual is not None:
        query = query.filter(EventoAcceso.lectura_manual == lectura_manual)
    if fecha_desde:
        query = query.filter(EventoAcceso.ocurrido_en >= fecha_desde)
    if fecha_hasta:
        query = query.filter(EventoAcceso.ocurrido_en <= fecha_hasta)

    total = query.with_entities(func.count(EventoAcceso.id)).scalar() or 0
    filas = (
        query.order_by(EventoAcceso.ocurrido_en.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        EventoAuditoriaItem(
            id=evento.id,
            placa=evento.placa,
            carril_id=evento.carril_id,
            sentido=carril_sentido,
            ocurrido_en=evento.ocurrido_en,
            confianza_lpr=evento.confianza_lpr,
            lectura_manual=evento.lectura_manual,
            foto_url=evento.foto_url,
        )
        for evento, carril_sentido in filas
    ]

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/cobros", response_model=PaginatedResponse[CobroAuditoriaItem])
def listar_cobros(
    placa: str | None = Query(default=None, description="Filtrar por placa"),
    estado: Literal["PENDIENTE", "PAGADO", "ANULADO", "VENCIDO"] | None = Query(
        default=None, description="Filtrar por estado del cobro"
    ),
    fecha_desde: date | None = Query(default=None),
    fecha_hasta: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CobroAuditoriaItem]:
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Rango de fechas inválido: "
                "fecha_desde no puede ser mayor que fecha_hasta."
                ),
        )

    query = db.query(Cobro)

    if placa:
        query = query.filter(Cobro.placa == placa.strip().upper())
    if estado:
        query = query.filter(Cobro.estado == estado)
    if fecha_desde:
        query = query.filter(Cobro.dia_operativo >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Cobro.dia_operativo <= fecha_hasta)

    total = query.with_entities(func.count(Cobro.id)).scalar() or 0
    cobros = (
        query.order_by(Cobro.dia_operativo.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [CobroAuditoriaItem.model_validate(c) for c in cobros]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)