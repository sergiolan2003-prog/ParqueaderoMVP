from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Query, Session

from app.core.config import settings
from app.modules.accesos.infrastructure.models import EventoAcceso
from app.modules.cobros.infrastructure.models import Cobro

EstadoCobro = Literal["PENDIENTE", "PAGADO", "ANULADO", "VENCIDO"]


def consultar_eventos(
    db: Session,
    *,
    placa: str | None,
    desde: date | None,
    hasta: date | None,
    page: int,
    page_size: int,
) -> tuple[list[EventoAcceso], int]:
    query = db.query(EventoAcceso)
    if placa:
        query = query.filter(EventoAcceso.placa == placa.strip().upper())
    zone = ZoneInfo(settings.operating_timezone)
    if desde is not None:
        inicio = datetime.combine(desde, time.min, tzinfo=zone)
        query = query.filter(EventoAcceso.ocurrido_en >= inicio)
    if hasta is not None:
        fin = datetime.combine(hasta, time.max, tzinfo=zone)
        query = query.filter(EventoAcceso.ocurrido_en <= fin)

    total = query.count()
    items = (
        query.order_by(EventoAcceso.ocurrido_en.desc(), EventoAcceso.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def consultar_cobros(
    db: Session,
    *,
    placa: str | None,
    desde: date | None,
    hasta: date | None,
    estado: EstadoCobro | None,
    page: int,
    page_size: int,
) -> tuple[list[Cobro], int]:
    query: Query = db.query(Cobro)
    if placa:
        query = query.filter(Cobro.placa == placa.strip().upper())
    if desde is not None:
        query = query.filter(Cobro.dia_operativo >= desde)
    if hasta is not None:
        query = query.filter(Cobro.dia_operativo <= hasta)
    if estado is not None:
        query = query.filter(Cobro.estado == estado)

    total = query.count()
    items = (
        query.order_by(Cobro.dia_operativo.desc(), Cobro.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def total_paginas(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size
