from typing import Protocol

from app.modules.cobros.domain.entities import Cobro


class CobroRepository(Protocol):
    def add(self, cobro: Cobro) -> bool: ...
