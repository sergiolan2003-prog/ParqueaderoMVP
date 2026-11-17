from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TarifaBase(BaseModel):
    sede_id: UUID
    tipo_vehiculo: Literal["CARRO", "MOTO"] = Field(
        ...,
        description="CARRO o MOTO",
    )
    franja: Literal["DIURNA", "NOCTURNA"] = Field(
        ...,
        description="DIURNA o NOCTURNA",
    )
    valor: Decimal = Field(..., ge=0, description="Valor de la tarifa")
    vigente_desde: date
    vigente_hasta: date | None = None

    @field_validator("tipo_vehiculo", "franja", mode="before")
    @classmethod
    def normalizar_codigo(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validar_vigencia(self) -> "TarifaBase":
        if self.vigente_hasta is not None and self.vigente_hasta < self.vigente_desde:
            raise ValueError("vigente_hasta no puede ser anterior a vigente_desde.")
        return self


class TarifaCreate(TarifaBase):
    pass


class TarifaResponse(TarifaBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
