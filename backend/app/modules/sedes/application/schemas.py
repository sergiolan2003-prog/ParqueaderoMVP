from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SedeResponse(BaseModel):
    id: UUID
    nombre: str
    cupos_carro: int
    cupos_moto: int

    model_config = ConfigDict(from_attributes=True)


class CuposUpdate(BaseModel):
    cupos_carro: int = Field(ge=0)
    cupos_moto: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")
