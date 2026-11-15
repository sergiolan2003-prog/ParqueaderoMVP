from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class Pago:
    id: UUID
    cobro_id: UUID
    medio: str
    valor: Decimal
    referencia_pasarela: str
    pagado_en: datetime
