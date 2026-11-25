from typing import Protocol
from uuid import UUID

from app.modules.pagos.domain.entities import Pago


class PagoRepository(Protocol):
    def add(self, pago: Pago) -> None: ...

    def get_by_reference(self, reference: str) -> Pago | None: ...

    def get_by_charge_id(self, charge_id: UUID) -> Pago | None: ...
