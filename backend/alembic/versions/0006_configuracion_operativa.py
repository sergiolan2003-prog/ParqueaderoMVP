"""Persist operational schedules and LPR confidence threshold.

Revision ID: 0006_configuracion_operativa
Revises: 0005_pago_efectivo_pase_cobro
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.modules.configuracion.infrastructure import constraints

revision: str = "0006_configuracion_operativa"
down_revision: Union[str, None] = "0005_pago_efectivo_pase_cobro"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "configuracion_operativa",
        sa.Column(
            "id",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("daytime_start", sa.Time(), nullable=False),
        sa.Column("daytime_end", sa.Time(), nullable=False),
        sa.Column("nighttime_start", sa.Time(), nullable=False),
        sa.Column("nighttime_end", sa.Time(), nullable=False),
        sa.Column("lpr_confidence_threshold", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "id = 1",
            name=op.f(
                "ck_configuracion_operativa_" + constraints.SINGLETON_ID,
            ),
        ),
        sa.CheckConstraint(
            "lpr_confidence_threshold >= 0 AND lpr_confidence_threshold <= 1",
            name=op.f(
                "ck_configuracion_operativa_" + constraints.LPR_CONFIDENCE_RANGE,
            ),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_configuracion_operativa"),
    )


def downgrade() -> None:
    op.drop_table("configuracion_operativa")
