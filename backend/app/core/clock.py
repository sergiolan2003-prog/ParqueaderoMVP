from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current timezone-aware instant in UTC."""
        ...


@dataclass(frozen=True)
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def __post_init__(self) -> None:
        if self.instant.tzinfo is None or self.instant.utcoffset() is None:
            raise ValueError("El instante del reloj fijo debe incluir zona horaria.")
        object.__setattr__(self, "instant", self.instant.astimezone(UTC))

    def now(self) -> datetime:
        return self.instant
