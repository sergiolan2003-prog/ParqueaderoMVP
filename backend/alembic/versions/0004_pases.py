"""Create pass validity records.

Revision ID: 0004_pases
Revises: 0003_usuario_auth
Create Date: 2026-11-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_pases"
down_revision: Union[str, None] = "0003_usuario_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pase",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("placa", sa.String(), nullable=False),
        sa.Column("sede_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vigente_desde", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "vigente_hasta >= vigente_desde",
            name=op.f("ck_pase_vigencia_order"),
        ),
        sa.ForeignKeyConstraint(
            ["placa"],
            ["vehiculo.placa"],
            name="fk_pase_placa_vehiculo",
        ),
        sa.ForeignKeyConstraint(
            ["sede_id"],
            ["sede.id"],
            name="fk_pase_sede_id_sede",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pase"),
    )
    op.create_index(
        "ix_pase_placa_sede_vigencia",
        "pase",
        ["placa", "sede_id", "vigente_desde", "vigente_hasta"],
    )


def downgrade() -> None:
    op.drop_index("ix_pase_placa_sede_vigencia", table_name="pase")
    op.drop_table("pase")