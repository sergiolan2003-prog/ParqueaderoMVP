from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.core.operating_day import OperatingDayConfiguration


class Settings(BaseSettings):
    app_name: str = Field(validation_alias="APP_NAME")
    app_env: str = Field(validation_alias="APP_ENV")
    database_url: str = Field(validation_alias="DATABASE_URL")
    operating_day_start: time = Field(validation_alias="OPERATING_DAY_START")
    daytime_start: time = Field(validation_alias="DAYTIME_START")
    daytime_end: time = Field(validation_alias="DAYTIME_END")
    nighttime_start: time = Field(validation_alias="NIGHTTIME_START")
    nighttime_end: time = Field(validation_alias="NIGHTTIME_END")
    operating_timezone: str = Field(validation_alias="OPERATING_TIMEZONE")
    lpr_confidence_threshold: float = Field(
        validation_alias="LPR_CONFIDENCE_THRESHOLD",
        ge=0,
        le=1,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def build_operating_day_configuration(
    source: Settings = settings,
) -> OperatingDayConfiguration:
    from app.core.operating_day import OperatingDayConfiguration, OperatingPeriod

    return OperatingDayConfiguration(
        operating_day_start=source.operating_day_start,
        periods=(
            OperatingPeriod(
                code="DIURNA",
                start=source.daytime_start,
                end=source.daytime_end,
            ),
            OperatingPeriod(
                code="NOCTURNA",
                start=source.nighttime_start,
                end=source.nighttime_end,
            ),
        ),
        timezone=source.operating_timezone,
    )
