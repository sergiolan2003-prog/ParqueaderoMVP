from typing import Protocol

from app.modules.pagos.domain.entities import Pago


class PagoRepository(Protocol):
    def add(self, pago: Pago) -> None: ...
