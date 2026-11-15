from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class Cobro:
    id: UUID
    placa: str
    sede_id: UUID
    dia_operativo: date
    tarifa_id: UUID
    valor: Decimal
    estado: str
