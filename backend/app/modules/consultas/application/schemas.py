from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventoConsultaResponse(BaseModel):
    id: UUID
    placa: str
    carril_id: UUID
    ocurrido_en: datetime
    confianza_lpr: float
    lectura_manual: bool
    foto_url: str | None

    model_config = ConfigDict(from_attributes=True)


class CobroConsultaResponse(BaseModel):
    id: UUID
    placa: str
    sede_id: UUID
    dia_operativo: date
    tarifa_id: UUID
    valor: Decimal
    estado: str

    model_config = ConfigDict(from_attributes=True)


class PaginaEventosResponse(BaseModel):
    items: list[EventoConsultaResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginaCobrosResponse(BaseModel):
    items: list[CobroConsultaResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
