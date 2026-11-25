from datetime import time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.core.operating_day import (
    OperatingDayConfiguration,
    OperatingDayConfigurationError,
    OperatingPeriod,
)


class ConfiguracionOperativaBase(BaseModel):
    daytime_start: time
    daytime_end: time
    nighttime_start: time
    nighttime_end: time
    lpr_confidence_threshold: float = Field(ge=0, le=1)

    @property
    def operating_periods(self) -> tuple[OperatingPeriod, OperatingPeriod]:
        return (
            OperatingPeriod(
                code="DIURNA",
                start=self.daytime_start,
                end=self.daytime_end,
            ),
            OperatingPeriod(
                code="NOCTURNA",
                start=self.nighttime_start,
                end=self.nighttime_end,
            ),
        )

    @model_validator(mode="after")
    def validate_periods(self) -> "ConfiguracionOperativaBase":
        try:
            OperatingDayConfiguration(
                operating_day_start=settings.operating_day_start,
                periods=self.operating_periods,
                timezone=settings.operating_timezone,
            )
        except OperatingDayConfigurationError as error:
            raise ValueError(str(error)) from error
        return self


class ConfiguracionOperativaUpdate(ConfiguracionOperativaBase):
    pass


class ConfiguracionOperativaResponse(ConfiguracionOperativaBase):
    model_config = ConfigDict(from_attributes=True)
