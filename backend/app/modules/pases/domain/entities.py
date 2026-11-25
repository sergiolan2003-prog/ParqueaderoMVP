from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class Pase:
    id: UUID
    cobro_id: UUID
    placa: str
    sede_id: UUID
    dia_operativo: date
    vigente_desde: datetime
    vigente_hasta: datetime

    def esta_vigente(self, instante: datetime) -> bool:
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError("El instante debe incluir zona horaria.")
        return self.vigente_desde <= instante < self.vigente_hasta
