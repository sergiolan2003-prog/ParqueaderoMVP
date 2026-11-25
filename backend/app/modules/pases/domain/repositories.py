from typing import Protocol
from uuid import UUID

from app.modules.pases.domain.entities import Pase


class PaseRepository(Protocol):
    def add(self, pase: Pase) -> None: ...

    def get_by_charge_id(self, charge_id: UUID) -> Pase | None: ...
