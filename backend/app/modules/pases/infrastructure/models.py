from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.pases.infrastructure import constraints


class Pase(Base):
    __tablename__ = "pase"
    __table_args__ = (
        CheckConstraint(
            "vigente_hasta >= vigente_desde",
            name="vigencia_order",
        ),
        UniqueConstraint("cobro_id", name=constraints.PASE_COBRO_UNIQUE),
        Index(
            "ix_pase_placa_sede_vigencia",
            "placa",
            "sede_id",
            "vigente_desde",
            "vigente_hasta",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    cobro_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cobro.id"),
        nullable=True,
    )
    dia_operativo: Mapped[date | None] = mapped_column(nullable=True)
    placa: Mapped[str] = mapped_column(
        ForeignKey("vehiculo.placa"),
        nullable=False,
    )
    sede_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("sede.id"),
        nullable=False,
    )
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    vigente_hasta: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
