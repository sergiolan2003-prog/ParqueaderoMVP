from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.tarifas.infrastructure import constraints


class Tarifa(Base):
    __tablename__ = "tarifa"
    __table_args__ = (
        CheckConstraint(
            "tipo_vehiculo IN ('CARRO', 'MOTO')",
            name=constraints.TARIFA_TIPO_VEHICULO_VALID,
        ),
        CheckConstraint(
            "franja IN ('DIURNA', 'NOCTURNA')",
            name=constraints.TARIFA_FRANJA_VALID,
        ),
        CheckConstraint(
            "valor >= 0",
            name=constraints.TARIFA_VALOR_NONNEGATIVE,
        ),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta >= vigente_desde",
            name=constraints.TARIFA_VIGENCIA_ORDER,
        ),
        UniqueConstraint(
            "sede_id",
            "tipo_vehiculo",
            "franja",
            "vigente_desde",
            name=constraints.TARIFA_SCOPE_START_UNIQUE,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    sede_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("sede.id"),
        nullable=False,
    )
    tipo_vehiculo: Mapped[str] = mapped_column(String, nullable=False)
    franja: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vigente_desde: Mapped[date] = mapped_column(Date, nullable=False)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
