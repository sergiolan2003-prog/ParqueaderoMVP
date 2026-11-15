from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.clock import Clock

_DAY_MICROSECONDS = 24 * 60 * 60 * 1_000_000
_ALLOWED_PERIOD_CODES = frozenset({"DIURNA", "NOCTURNA"})


class OperatingDayConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class OperatingPeriod:
    code: str
    start: time
    end: time


@dataclass(frozen=True)
class OperatingDayConfiguration:
    operating_day_start: time
    periods: tuple[OperatingPeriod, ...]
    timezone: str
    zone: ZoneInfo = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        try:
            zone = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise OperatingDayConfigurationError(
                f"Zona horaria desconocida: {self.timezone}."
            ) from error
        object.__setattr__(self, "zone", zone)

        self._validate_time(self.operating_day_start, "inicio del día operativo")
        self._validate_periods()

    def _validate_periods(self) -> None:
        if not self.periods:
            raise OperatingDayConfigurationError(
                "La configuración debe incluir franjas que cubran las 24 horas."
            )

        codes = [period.code for period in self.periods]
        if len(set(codes)) != len(codes):
            raise OperatingDayConfigurationError(
                "Los códigos de franja no pueden repetirse."
            )
        if set(codes) != _ALLOWED_PERIOD_CODES:
            raise OperatingDayConfigurationError(
                "Las franjas deben usar exactamente los códigos DIURNA y NOCTURNA."
            )

        segments: list[tuple[int, int]] = []
        for period in self.periods:
            self._validate_time(period.start, f"inicio de {period.code}")
            self._validate_time(period.end, f"fin de {period.code}")

            start = self._microseconds_since_midnight(period.start)
            end = self._microseconds_since_midnight(period.end)
            if start == end:
                raise OperatingDayConfigurationError(
                    f"La franja {period.code} no puede tener duración cero."
                )
            if start < end:
                segments.append((start, end))
            else:
                segments.extend(((start, _DAY_MICROSECONDS), (0, end)))

        covered_until = 0
        for start, end in sorted(segments):
            if start < covered_until:
                raise OperatingDayConfigurationError(
                    "Las franjas horarias se solapan."
                )
            if start > covered_until:
                raise OperatingDayConfigurationError(
                    "Las franjas horarias dejan huecos."
                )
            covered_until = end

        if covered_until != _DAY_MICROSECONDS:
            raise OperatingDayConfigurationError(
                "Las franjas horarias deben cubrir las 24 horas sin huecos."
            )

    @staticmethod
    def _validate_time(value: time, description: str) -> None:
        if not isinstance(value, time) or value.tzinfo is not None:
            raise OperatingDayConfigurationError(
                f"El {description} debe ser una hora local sin zona horaria."
            )

    @staticmethod
    def _microseconds_since_midnight(value: time) -> int:
        return (
            ((value.hour * 60 + value.minute) * 60 + value.second) * 1_000_000
            + value.microsecond
        )


class OperatingDayService:
    def __init__(
        self, clock: Clock, configuration: OperatingDayConfiguration
    ) -> None:
        self._clock = clock
        self._configuration = configuration

    def dia_operativo(self, instante: datetime | None = None) -> date:
        local_instant = self._to_local(instante)
        local_time = local_instant.time().replace(tzinfo=None)
        if local_time < self._configuration.operating_day_start:
            return local_instant.date() - timedelta(days=1)
        return local_instant.date()

    def franja(self, instante: datetime | None = None) -> str:
        local_time = self._to_local(instante).time().replace(tzinfo=None)
        for period in self._configuration.periods:
            if self._contains(period, local_time):
                return period.code
        raise OperatingDayConfigurationError(
            "La configuración no asigna una franja a la hora local."
        )

    def _to_local(self, instante: datetime | None) -> datetime:
        instant = self._clock.now() if instante is None else instante
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("El instante debe incluir zona horaria.")
        return instant.astimezone(self._configuration.zone)

    @staticmethod
    def _contains(period: OperatingPeriod, local_time: time) -> bool:
        if period.start < period.end:
            return period.start <= local_time < period.end
        return local_time >= period.start or local_time < period.end
