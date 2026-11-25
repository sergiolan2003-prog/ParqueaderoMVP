"""Associate a single payment and pass with each charge.

Revision ID: 0005_pago_efectivo_pase_cobro
Revises: 0004_pases
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.pagos.infrastructure import constraints as pagos_constraints
from app.modules.pases.infrastructure import constraints as pases_constraints

revision: str = "0005_pago_efectivo_pase_cobro"
down_revision: Union[str, None] = "0004_pases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT cobro_id
                FROM pago
                GROUP BY cobro_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'No se puede aplicar HU-11: hay cobros con más de un pago.';
            END IF;
        END
        $$;
        """
    )

    op.add_column(
        "pase",
        sa.Column("cobro_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "pase",
        sa.Column("dia_operativo", sa.Date(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pase_cobro_id_cobro",
        "pase",
        "cobro",
        ["cobro_id"],
        ["id"],
    )
    op.create_unique_constraint(
        pases_constraints.PASE_COBRO_UNIQUE,
        "pase",
        ["cobro_id"],
    )
    op.create_unique_constraint(
        pagos_constraints.PAGO_COBRO_UNIQUE,
        "pago",
        ["cobro_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        pagos_constraints.PAGO_COBRO_UNIQUE,
        "pago",
        type_="unique",
    )
    op.drop_constraint(
        pases_constraints.PASE_COBRO_UNIQUE,
        "pase",
        type_="unique",
    )
    op.drop_constraint("fk_pase_cobro_id_cobro", "pase", type_="foreignkey")
    op.drop_column("pase", "dia_operativo")
    op.drop_column("pase", "cobro_id")
