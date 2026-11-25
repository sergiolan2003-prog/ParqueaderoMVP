from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class EventoAuditoriaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    placa: str
    carril_id: UUID
    sentido: str
    ocurrido_en: datetime
    confianza_lpr: float
    lectura_manual: bool
    foto_url: str | None = None


class CobroAuditoriaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    placa: str
    sede_id: UUID
    dia_operativo: date
    tarifa_id: UUID
    valor: Decimal
    estado: str