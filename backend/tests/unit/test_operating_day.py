import subprocess
import sys
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.clock import FixedClock, SystemClock
from app.core.config import Settings, build_operating_day_configuration, settings
from app.core.operating_day import (
    OperatingDayConfiguration,
    OperatingDayConfigurationError,
    OperatingDayService,
    OperatingPeriod,
)


@pytest.fixture
def service() -> OperatingDayService:
    return OperatingDayService(
        clock=FixedClock(datetime(2026, 2, 20, 13, tzinfo=UTC)),
        configuration=build_operating_day_configuration(settings),
    )


@pytest.mark.parametrize(
    ("local_time", "instant", "expected_day", "expected_period"),
    [
        (
            "05:50",
            datetime(2026, 2, 20, 10, 50, tzinfo=UTC),
            date(2026, 2, 19),
            "NOCTURNA",
        ),
        (
            "05:59",
            datetime(2026, 2, 20, 10, 59, tzinfo=UTC),
            date(2026, 2, 19),
            "NOCTURNA",
        ),
        (
            "06:00",
            datetime(2026, 2, 20, 11, 0, tzinfo=UTC),
            date(2026, 2, 20),
            "DIURNA",
        ),
        (
            "08:00",
            datetime(2026, 2, 20, 13, 0, tzinfo=UTC),
            date(2026, 2, 20),
            "DIURNA",
        ),
        (
            "17:59",
            datetime(2026, 2, 20, 22, 59, tzinfo=UTC),
            date(2026, 2, 20),
            "DIURNA",
        ),
        (
            "18:00",
            datetime(2026, 2, 20, 23, 0, tzinfo=UTC),
            date(2026, 2, 20),
            "NOCTURNA",
        ),
        (
            "19:00",
            datetime(2026, 2, 21, 0, 0, tzinfo=UTC),
            date(2026, 2, 20),
            "NOCTURNA",
        ),
        (
            "23:00",
            datetime(2026, 2, 21, 4, 0, tzinfo=UTC),
            date(2026, 2, 20),
            "NOCTURNA",
        ),
        (
            "01:00 (día siguiente)",
            datetime(2026, 2, 21, 6, 0, tzinfo=UTC),
            date(2026, 2, 20),
            "NOCTURNA",
        ),
    ],
)
def test_operating_day_and_period_boundaries(
    service: OperatingDayService,
    local_time: str,
    instant: datetime,
    expected_day: date,
    expected_period: str,
) -> None:
    assert service.dia_operativo(instant) == expected_day, local_time
    assert service.franja(instant) == expected_period, local_time


def test_utc_instant_is_converted_to_bogota(service: OperatingDayService) -> None:
    instant = datetime(2026, 2, 20, 10, 0, tzinfo=UTC)

    assert service.franja(instant) == "NOCTURNA"
    assert service.dia_operativo(instant) == date(2026, 2, 19)


def test_service_uses_injected_fixed_clock() -> None:
    fixed_clock = FixedClock(datetime(2026, 2, 21, 10, 50, tzinfo=UTC))
    service = OperatingDayService(
        clock=fixed_clock,
        configuration=build_operating_day_configuration(settings),
    )

    assert service.dia_operativo() == date(2026, 2, 20)
    assert service.franja() == "NOCTURNA"


def test_system_clock_returns_aware_utc_instant() -> None:
    assert SystemClock().now().tzinfo is UTC


def test_settings_reject_lpr_confidence_outside_zero_to_one() -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_NAME="Parqueadero API",
            APP_ENV="test",
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            OPERATING_DAY_START="06:00",
            DAYTIME_START="06:00",
            DAYTIME_END="18:00",
            NIGHTTIME_START="18:00",
            NIGHTTIME_END="06:00",
            OPERATING_TIMEZONE="America/Bogota",
            LPR_CONFIDENCE_THRESHOLD=1.1,
        )


@pytest.mark.parametrize(
    ("periods", "message"),
    [
        (
            (
                OperatingPeriod("DIURNA", time(6), time(19)),
                OperatingPeriod("NOCTURNA", time(18), time(6)),
            ),
            "solapan",
        ),
        (
            (
                OperatingPeriod("DIURNA", time(6), time(17)),
                OperatingPeriod("NOCTURNA", time(18), time(6)),
            ),
            "huecos",
        ),
        (
            (
                OperatingPeriod("DIURNA", time(6), time(18)),
                OperatingPeriod("DIURNA", time(18), time(6)),
            ),
            "no pueden repetirse",
        ),
    ],
)
def test_rejects_invalid_period_configuration(
    periods: tuple[OperatingPeriod, ...], message: str
) -> None:
    with pytest.raises(OperatingDayConfigurationError, match=message):
        OperatingDayConfiguration(
            operating_day_start=time(6),
            periods=periods,
            timezone="America/Bogota",
        )


def test_domain_module_does_not_import_framework_or_orm() -> None:
    backend_directory = Path(__file__).resolve().parents[2]
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import app.core.operating_day; "
                "assert 'sqlalchemy' not in sys.modules; "
                "assert 'fastapi' not in sys.modules"
            ),
        ],
        check=True,
        cwd=backend_directory,
        capture_output=True,
        text=True,
    )
