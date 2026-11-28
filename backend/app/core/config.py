from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.core.operating_day import OperatingDayConfiguration, OperatingPeriod


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
    lpr_reader_type: str = Field(
        default="SIMULADO",
        validation_alias="LPR_READER_TYPE",
    )
    lpr_image_storage_path: str = Field(
        validation_alias="LPR_IMAGE_STORAGE_PATH",
    )
    lpr_image_max_bytes: int = Field(
        validation_alias="LPR_IMAGE_MAX_BYTES",
        gt=0,
    )
    jwt_secret: str = Field(
        validation_alias="JWT_SECRET",
        min_length=32,
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
    )
    jwt_expire_minutes: int = Field(
        default=60,
        validation_alias="JWT_EXPIRE_MINUTES",
        gt=0,
    )
    seed_admin_username: str = Field(validation_alias="SEED_ADMIN_USERNAME")
    seed_admin_password: str = Field(validation_alias="SEED_ADMIN_PASSWORD")
    seed_operador_username: str = Field(validation_alias="SEED_OPERADOR_USERNAME")
    seed_operador_password: str = Field(validation_alias="SEED_OPERADOR_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def build_operating_day_configuration(
    source: Settings = settings,
    periods: tuple[OperatingPeriod, ...] | None = None,
) -> OperatingDayConfiguration:
    from app.core.operating_day import OperatingDayConfiguration, OperatingPeriod

    return OperatingDayConfiguration(
        operating_day_start=source.operating_day_start,
        periods=periods
        if periods is not None
        else (
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
