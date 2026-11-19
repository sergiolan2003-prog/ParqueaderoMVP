from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.auth.infrastructure import constraints


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        UniqueConstraint(
            "username",
            name=constraints.USUARIO_USERNAME_UNIQUE,
        ),
        CheckConstraint(
            "rol IN ('OPERADOR', 'ADMINISTRADOR')",
            name=constraints.USUARIO_ROL_VALID,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    rol: Mapped[str] = mapped_column(String, nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
