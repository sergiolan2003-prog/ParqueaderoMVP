from datetime import time

from sqlalchemy import CheckConstraint, Float, SmallInteger, Time, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.configuracion.infrastructure import constraints


class ConfiguracionOperativa(Base):
    __tablename__ = "configuracion_operativa"
    __table_args__ = (
        CheckConstraint(
            "id = 1",
            name=constraints.SINGLETON_ID,
        ),
        CheckConstraint(
            "lpr_confidence_threshold >= 0 AND lpr_confidence_threshold <= 1",
            name=constraints.LPR_CONFIDENCE_RANGE,
        ),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        server_default=text("1"),
    )
    daytime_start: Mapped[time] = mapped_column(Time, nullable=False)
    daytime_end: Mapped[time] = mapped_column(Time, nullable=False)
    nighttime_start: Mapped[time] = mapped_column(Time, nullable=False)
    nighttime_end: Mapped[time] = mapped_column(Time, nullable=False)
    lpr_confidence_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
