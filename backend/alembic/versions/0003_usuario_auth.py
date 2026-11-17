"""Add authentication users.

Revision ID: 0003_usuario_auth
Revises: 0002_modelo_datos
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.auth.infrastructure import constraints

revision: str = "0003_usuario_auth"
down_revision: Union[str, None] = "0002_modelo_datos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("rol", sa.String(), nullable=False),
        sa.Column(
            "activo",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usuario"),
        sa.UniqueConstraint(
            "username",
            name=constraints.USUARIO_USERNAME_UNIQUE,
        ),
        sa.CheckConstraint(
            "rol IN ('OPERADOR', 'ADMINISTRADOR')",
            name=constraints.USUARIO_ROL_VALID,
        ),
    )


def downgrade() -> None:
    op.drop_table("usuario")
