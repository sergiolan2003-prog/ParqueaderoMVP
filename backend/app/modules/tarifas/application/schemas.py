from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TarifaBase(BaseModel):
    sede_id: UUID
    tipo_vehiculo: str = Field(..., description="CARRO o MOTO")
    franja: str = Field(..., description="DIURNA o NOCTURNA")
    valor: Decimal = Field(..., ge=0, description="Valor de la tarifa")
    vigente_desde: date
    vigente_hasta: Optional[date] = None


class TarifaCreate(TarifaBase):
    pass


class TarifaResponse(TarifaBase):
    id: UUID

    class Config:
        from_attributes = True
