from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.pagos.infrastructure import constraints


class Pago(Base):
    __tablename__ = "pago"
    __table_args__ = (
        CheckConstraint(
            "medio IN ('EFECTIVO', 'TARJETA', 'PSE', 'NEQUI')",
            name=constraints.PAGO_MEDIO_VALID,
        ),
        CheckConstraint(
            "valor > 0",
            name=constraints.PAGO_VALOR_POSITIVE,
        ),
        UniqueConstraint(
            "referencia_pasarela",
            name=constraints.PAGO_REFERENCIA_UNIQUE,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    cobro_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cobro.id"),
        nullable=False,
    )
    medio: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    referencia_pasarela: Mapped[str] = mapped_column(String, nullable=False)
    pagado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
