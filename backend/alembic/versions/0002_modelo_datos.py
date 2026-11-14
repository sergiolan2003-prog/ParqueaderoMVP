"""Create the parqueadero data model.

Revision ID: 0002_modelo_datos
Revises: 0001_initial
Create Date: 2026-11-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.accesos.infrastructure import constraints as accesos_constraints
from app.modules.cobros.infrastructure import constraints as cobros_constraints
from app.modules.pagos.infrastructure import constraints as pagos_constraints
from app.modules.tarifas.infrastructure import constraints as tarifas_constraints

revision: str = "0002_modelo_datos"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sede",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("zona_horaria", sa.String(), nullable=False),
        sa.Column("inicio_dia_operativo", sa.Time(), nullable=False),
        sa.Column("cupos_carro", sa.Integer(), nullable=False),
        sa.Column("cupos_moto", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "cupos_carro >= 0",
            name=op.f(f"ck_sede_{accesos_constraints.SEDE_CUPOS_CARRO_NONNEGATIVE}"),
        ),
        sa.CheckConstraint(
            "cupos_moto >= 0",
            name=op.f(f"ck_sede_{accesos_constraints.SEDE_CUPOS_MOTO_NONNEGATIVE}"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sede"),
        sa.UniqueConstraint(
            "nombre",
            name=accesos_constraints.SEDE_NOMBRE_UNIQUE,
        ),
    )
    op.create_table(
        "carril",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("sede_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sentido", sa.String(), nullable=False),
        sa.CheckConstraint(
            "sentido IN ('ENTRADA', 'SALIDA')",
            name=op.f(f"ck_carril_{accesos_constraints.CARRIL_SENTIDO_VALID}"),
        ),
        sa.ForeignKeyConstraint(
            ["sede_id"],
            ["sede.id"],
            name="fk_carril_sede_id_sede",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_carril"),
    )
    op.create_table(
        "vehiculo",
        sa.Column("placa", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.CheckConstraint(
            "placa = upper(placa)",
            name=op.f(f"ck_vehiculo_{accesos_constraints.VEHICULO_PLACA_UPPERCASE}"),
        ),
        sa.CheckConstraint(
            "tipo IN ('CARRO', 'MOTO')",
            name=op.f(f"ck_vehiculo_{accesos_constraints.VEHICULO_TIPO_VALID}"),
        ),
        sa.PrimaryKeyConstraint("placa", name="pk_vehiculo"),
    )
    op.create_table(
        "evento_acceso",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("placa", sa.String(), nullable=False),
        sa.Column("carril_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confianza_lpr", sa.Float(), nullable=False),
        sa.Column(
            "lectura_manual",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("foto_url", sa.String(), nullable=True),
        sa.CheckConstraint(
            "confianza_lpr >= 0 AND confianza_lpr <= 1",
            name=op.f(f"ck_evento_acceso_{accesos_constraints.EVENTO_CONFIANZA_RANGE}"),
        ),
        sa.ForeignKeyConstraint(
            ["carril_id"],
            ["carril.id"],
            name="fk_evento_acceso_carril_id_carril",
        ),
        sa.ForeignKeyConstraint(
            ["placa"],
            ["vehiculo.placa"],
            name="fk_evento_acceso_placa_vehiculo",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evento_acceso"),
    )
    op.create_table(
        "tarifa",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("sede_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo_vehiculo", sa.String(), nullable=False),
        sa.Column("franja", sa.String(), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("vigente_desde", sa.Date(), nullable=False),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "tipo_vehiculo IN ('CARRO', 'MOTO')",
            name=op.f(f"ck_tarifa_{tarifas_constraints.TARIFA_TIPO_VEHICULO_VALID}"),
        ),
        sa.CheckConstraint(
            "franja IN ('DIURNA', 'NOCTURNA')",
            name=op.f(f"ck_tarifa_{tarifas_constraints.TARIFA_FRANJA_VALID}"),
        ),
        sa.CheckConstraint(
            "valor >= 0",
            name=op.f(f"ck_tarifa_{tarifas_constraints.TARIFA_VALOR_NONNEGATIVE}"),
        ),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta >= vigente_desde",
            name=op.f(f"ck_tarifa_{tarifas_constraints.TARIFA_VIGENCIA_ORDER}"),
        ),
        sa.ForeignKeyConstraint(
            ["sede_id"],
            ["sede.id"],
            name="fk_tarifa_sede_id_sede",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tarifa"),
        sa.UniqueConstraint(
            "sede_id",
            "tipo_vehiculo",
            "franja",
            "vigente_desde",
            name=tarifas_constraints.TARIFA_SCOPE_START_UNIQUE,
        ),
    )
    op.create_table(
        "cobro",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("placa", sa.String(), nullable=False),
        sa.Column("sede_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dia_operativo", sa.Date(), nullable=False),
        sa.Column("tarifa_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.CheckConstraint(
            "valor >= 0",
            name=op.f(f"ck_cobro_{cobros_constraints.COBRO_VALOR_NONNEGATIVE}"),
        ),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'PAGADO', 'ANULADO', 'VENCIDO')",
            name=op.f(f"ck_cobro_{cobros_constraints.COBRO_ESTADO_VALID}"),
        ),
        sa.ForeignKeyConstraint(
            ["placa"],
            ["vehiculo.placa"],
            name="fk_cobro_placa_vehiculo",
        ),
        sa.ForeignKeyConstraint(
            ["sede_id"],
            ["sede.id"],
            name="fk_cobro_sede_id_sede",
        ),
        sa.ForeignKeyConstraint(
            ["tarifa_id"],
            ["tarifa.id"],
            name="fk_cobro_tarifa_id_tarifa",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cobro"),
        sa.UniqueConstraint(
            "placa",
            "sede_id",
            "dia_operativo",
            name=cobros_constraints.COBRO_PLACA_SEDE_DIA_UNIQUE,
        ),
    )
    op.create_table(
        "pago",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cobro_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medio", sa.String(), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("referencia_pasarela", sa.String(), nullable=False),
        sa.Column("pagado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "medio IN ('EFECTIVO', 'TARJETA', 'PSE', 'NEQUI')",
            name=op.f(f"ck_pago_{pagos_constraints.PAGO_MEDIO_VALID}"),
        ),
        sa.CheckConstraint(
            "valor > 0",
            name=op.f(f"ck_pago_{pagos_constraints.PAGO_VALOR_POSITIVE}"),
        ),
        sa.ForeignKeyConstraint(
            ["cobro_id"],
            ["cobro.id"],
            name="fk_pago_cobro_id_cobro",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pago"),
        sa.UniqueConstraint(
            "referencia_pasarela",
            name=pagos_constraints.PAGO_REFERENCIA_UNIQUE,
        ),
    )


def downgrade() -> None:
    op.drop_table("pago")
    op.drop_table("cobro")
    op.drop_table("tarifa")
    op.drop_table("evento_acceso")
    op.drop_table("vehiculo")
    op.drop_table("carril")
    op.drop_table("sede")
