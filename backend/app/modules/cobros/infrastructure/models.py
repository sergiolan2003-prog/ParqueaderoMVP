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
from app.modules.cobros.infrastructure import constraints


class Cobro(Base):
    __tablename__ = "cobro"
    __table_args__ = (
        CheckConstraint(
            "valor >= 0",
            name=constraints.COBRO_VALOR_NONNEGATIVE,
        ),
        CheckConstraint(
            "estado IN ('PENDIENTE', 'PAGADO', 'ANULADO', 'VENCIDO')",
            name=constraints.COBRO_ESTADO_VALID,
        ),
        UniqueConstraint(
            "placa",
            "sede_id",
            "dia_operativo",
            name=constraints.COBRO_PLACA_SEDE_DIA_UNIQUE,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    placa: Mapped[str] = mapped_column(
        String,
        ForeignKey("vehiculo.placa"),
        nullable=False,
    )
    sede_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("sede.id"),
        nullable=False,
    )
    dia_operativo: Mapped[date] = mapped_column(Date, nullable=False)
    tarifa_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tarifa.id"),
        nullable=False,
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False)
