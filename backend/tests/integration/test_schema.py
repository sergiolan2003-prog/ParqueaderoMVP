import os
import subprocess
import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.accesos.infrastructure.models import Sede, Vehiculo
from app.modules.cobros.domain.entities import Cobro as CobroEntity
from app.modules.cobros.domain.exceptions import CobroDuplicadoError
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.cobros.infrastructure.repositories import SqlAlchemyCobroRepository
from app.modules.pagos.domain.entities import Pago as PagoEntity
from app.modules.pagos.domain.exceptions import PagoDuplicadoError
from app.modules.pagos.infrastructure.models import Pago
from app.modules.pagos.infrastructure.repositories import SqlAlchemyPagoRepository
from app.modules.tarifas.infrastructure.models import Tarifa

BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPECTED_TABLES = {
    "sede",
    "carril",
    "vehiculo",
    "evento_acceso",
    "tarifa",
    "cobro",
    "pago",
}


def _new_sede(name: str | None = None) -> Sede:
    return Sede(
        nombre=name or f"Sede-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(0, 0),
        cupos_carro=20,
        cupos_moto=10,
    )


def _new_tarifa(sede_id, *, start: date = date(2026, 1, 1)) -> Tarifa:
    return Tarifa(
        sede_id=sede_id,
        tipo_vehiculo="CARRO",
        franja="DIURNA",
        valor=Decimal("12000.00"),
        vigente_desde=start,
        vigente_hasta=None,
    )


def _seed(session: Session):
    sede = _new_sede()
    vehiculo = Vehiculo(placa="ABC123", tipo="CARRO")
    session.add_all([sede, vehiculo])
    session.flush()

    tarifa = _new_tarifa(sede.id)
    session.add(tarifa)
    session.flush()

    cobro = Cobro(
        placa=vehiculo.placa,
        sede_id=sede.id,
        dia_operativo=date(2026, 3, 10),
        tarifa_id=tarifa.id,
        valor=tarifa.valor,
        estado="PENDIENTE",
    )
    session.add(cobro)
    session.flush()
    return sede, vehiculo, tarifa, cobro


def _check_constraint_name(error: IntegrityError) -> str | None:
    return error.orig.diag.constraint_name


def test_migrations_work_from_empty_database(
    disposable_migration_database,
    migration_runner,
) -> None:
    database_url = disposable_migration_database
    migration_runner(database_url, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert EXPECTED_TABLES <= set(inspect(connection).get_table_names())

        migration_runner(database_url, "base")
        with engine.connect() as connection:
            assert not EXPECTED_TABLES.intersection(inspect(connection).get_table_names())

        migration_runner(database_url, "head")
        with engine.connect() as connection:
            assert EXPECTED_TABLES <= set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def test_valid_sede_vehicle_tarifa_cobro_and_pago_are_inserted(db_session: Session) -> None:
    _, _, tarifa, cobro = _seed(db_session)
    pago = Pago(
        cobro_id=cobro.id,
        medio="EFECTIVO",
        valor=Decimal("12000.00"),
        referencia_pasarela="efectivo-unique-001",
        pagado_en=datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(pago)
    db_session.flush()

    assert cobro.tarifa_id == tarifa.id
    assert pago.id is not None


def test_duplicate_cobro_is_rejected_by_database_and_repository(
    db_session: Session,
) -> None:
    sede, vehiculo, tarifa, cobro = _seed(db_session)
    duplicate = Cobro(
        placa=vehiculo.placa,
        sede_id=sede.id,
        dia_operativo=cobro.dia_operativo,
        tarifa_id=tarifa.id,
        valor=tarifa.valor,
        estado="PENDIENTE",
    )

    with pytest.raises(IntegrityError) as database_error:
        with db_session.begin_nested():
            db_session.add(duplicate)
            db_session.flush()
    assert _check_constraint_name(database_error.value) == "uq_cobro_placa_sede_dia"

    duplicate_entity = CobroEntity(
        id=uuid4(),
        placa=vehiculo.placa,
        sede_id=sede.id,
        dia_operativo=cobro.dia_operativo,
        tarifa_id=tarifa.id,
        valor=tarifa.valor,
        estado="PENDIENTE",
    )
    with pytest.raises(CobroDuplicadoError) as repository_error:
        with db_session.begin_nested():
            SqlAlchemyCobroRepository(db_session).add(duplicate_entity)
    assert isinstance(repository_error.value.__cause__, IntegrityError)


def test_same_plate_on_another_day_or_at_another_site_is_accepted(
    db_session: Session,
) -> None:
    sede, vehiculo, tarifa, cobro = _seed(db_session)
    other_sede = _new_sede()
    db_session.add(other_sede)
    db_session.flush()
    other_tarifa = _new_tarifa(other_sede.id)
    db_session.add(other_tarifa)
    db_session.flush()

    db_session.add_all(
        [
            Cobro(
                placa=vehiculo.placa,
                sede_id=sede.id,
                dia_operativo=date(2026, 3, 11),
                tarifa_id=tarifa.id,
                valor=tarifa.valor,
                estado="PENDIENTE",
            ),
            Cobro(
                placa=vehiculo.placa,
                sede_id=other_sede.id,
                dia_operativo=cobro.dia_operativo,
                tarifa_id=other_tarifa.id,
                valor=other_tarifa.valor,
                estado="PENDIENTE",
            ),
        ]
    )
    db_session.flush()


def test_duplicate_payment_reference_is_rejected_by_database_and_repository(
    db_session: Session,
) -> None:
    _, _, _, cobro = _seed(db_session)
    payment = Pago(
        cobro_id=cobro.id,
        medio="PSE",
        valor=Decimal("12000.00"),
        referencia_pasarela="pse-reference-001",
        pagado_en=datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(payment)
    db_session.flush()

    duplicate = Pago(
        cobro_id=cobro.id,
        medio="PSE",
        valor=Decimal("12000.00"),
        referencia_pasarela=payment.referencia_pasarela,
        pagado_en=datetime(2026, 3, 10, 12, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(IntegrityError) as database_error:
        with db_session.begin_nested():
            db_session.add(duplicate)
            db_session.flush()
    assert _check_constraint_name(database_error.value) == "uq_pago_referencia"

    duplicate_entity = PagoEntity(
        id=uuid4(),
        cobro_id=cobro.id,
        medio="PSE",
        valor=Decimal("12000.00"),
        referencia_pasarela=payment.referencia_pasarela,
        pagado_en=datetime(2026, 3, 10, 12, 2, tzinfo=timezone.utc),
    )
    with pytest.raises(PagoDuplicadoError) as repository_error:
        with db_session.begin_nested():
            SqlAlchemyPagoRepository(db_session).add(duplicate_entity)
    assert isinstance(repository_error.value.__cause__, IntegrityError)


def test_required_tarifa_and_named_checks_and_uniqueness_are_enforced(
    db_session: Session,
) -> None:
    sede, vehiculo, tarifa, cobro = _seed(db_session)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                Cobro(
                    placa=vehiculo.placa,
                    sede_id=sede.id,
                    dia_operativo=date(2026, 3, 12),
                    tarifa_id=None,
                    valor=tarifa.valor,
                    estado="PENDIENTE",
                )
            )
            db_session.flush()

    invalid_vigencia = _new_tarifa(sede.id, start=date(2026, 4, 2))
    invalid_vigencia.vigente_hasta = date(2026, 4, 1)
    with pytest.raises(IntegrityError) as vigencia_error:
        with db_session.begin_nested():
            db_session.add(invalid_vigencia)
            db_session.flush()
    assert _check_constraint_name(vigencia_error.value) == "ck_tarifa_vigencia_order"

    duplicate_tarifa = _new_tarifa(sede.id)
    with pytest.raises(IntegrityError) as tarifa_error:
        with db_session.begin_nested():
            db_session.add(duplicate_tarifa)
            db_session.flush()
    assert (
        _check_constraint_name(tarifa_error.value)
        == "uq_tarifa_sede_tipo_franja_desde"
    )

    invalid_state = Cobro(
        placa=vehiculo.placa,
        sede_id=sede.id,
        dia_operativo=date(2026, 3, 12),
        tarifa_id=tarifa.id,
        valor=tarifa.valor,
        estado="DESCONOCIDO",
    )
    with pytest.raises(IntegrityError) as state_error:
        with db_session.begin_nested():
            db_session.add(invalid_state)
            db_session.flush()
    assert _check_constraint_name(state_error.value) == "ck_cobro_estado_valid"


def test_lowercase_vehicle_plate_is_rejected_by_check(db_session: Session) -> None:
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            db_session.add(Vehiculo(placa="abc123", tipo="CARRO"))
            db_session.flush()
    assert _check_constraint_name(error.value) == "ck_vehiculo_placa_uppercase"


def test_alembic_offline_sql_contains_cobro_and_unique_constraint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        check=True,
        text=True,
    )

    assert "CREATE TABLE cobro" in result.stdout
    assert "uq_cobro_placa_sede_dia" in result.stdout
