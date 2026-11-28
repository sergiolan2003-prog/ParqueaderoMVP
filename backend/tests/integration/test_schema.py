import os
import subprocess
import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.accesos.infrastructure.models import Carril, Sede, Vehiculo
from app.modules.auth.domain.entities import Rol
from app.modules.auth.domain.entities import Usuario as UsuarioEntity
from app.modules.auth.domain.exceptions import UsuarioDuplicadoError
from app.modules.auth.infrastructure.models import Usuario
from app.modules.auth.infrastructure.passwords import Argon2PasswordHasher
from app.modules.auth.infrastructure.repositories import SqlAlchemyUsuarioRepository
from app.modules.auth.infrastructure.seed import (
    seed_development_data,
    seed_users,
)
from app.modules.cobros.domain.entities import Cobro as CobroEntity
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.cobros.infrastructure.repositories import SqlAlchemyCobroRepository
from app.modules.pagos.domain.entities import Pago as PagoEntity
from app.modules.pagos.domain.exceptions import PagoDuplicadoError
from app.modules.pagos.infrastructure.models import Pago
from app.modules.pagos.infrastructure.repositories import SqlAlchemyPagoRepository
from app.modules.pases.infrastructure.models import Pase
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
    "usuario",
    "pase",
    "configuracion_operativa",
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
            assert not EXPECTED_TABLES.intersection(
                inspect(connection).get_table_names()
            )

        migration_runner(database_url, "head")
        with engine.connect() as connection:
            assert EXPECTED_TABLES <= set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def test_hu11_migration_preserves_legacy_payment_and_pass(
    disposable_migration_database,
    migration_runner,
) -> None:
    database_url = disposable_migration_database
    migration_runner(database_url, "0004_pases")
    engine = create_engine(database_url)
    sede_id = uuid4()
    cobro_id = uuid4()
    tarifa_id = uuid4()
    pago_id = uuid4()
    pase_id = uuid4()
    pagado_en = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO sede "
                    "(id, nombre, zona_horaria, inicio_dia_operativo, "
                    "cupos_carro, cupos_moto) "
                    "VALUES (:id, :nombre, :zona, :inicio, :carros, :motos)"
                ),
                {
                    "id": sede_id,
                    "nombre": "HU11-legacy",
                    "zona": "America/Bogota",
                    "inicio": time(6),
                    "carros": 10,
                    "motos": 5,
                },
            )
            connection.execute(
                sa.text("INSERT INTO vehiculo (placa, tipo) VALUES (:placa, :tipo)"),
                {"placa": "LEG123", "tipo": "CARRO"},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO tarifa "
                    "(id, sede_id, tipo_vehiculo, franja, valor, vigente_desde) "
                    "VALUES (:id, :sede, 'CARRO', 'DIURNA', 12000, :desde)"
                ),
                {
                    "id": tarifa_id,
                    "sede": sede_id,
                    "desde": date(2026, 1, 1),
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cobro "
                    "(id, placa, sede_id, dia_operativo, tarifa_id, valor, estado) "
                    "VALUES (:id, 'LEG123', :sede, :dia, :tarifa, 12000, 'PAGADO')"
                ),
                {
                    "id": cobro_id,
                    "sede": sede_id,
                    "dia": date(2026, 3, 10),
                    "tarifa": tarifa_id,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO pago "
                    "(id, cobro_id, medio, valor, referencia_pasarela, pagado_en) "
                    "VALUES (:id, :cobro, 'EFECTIVO', 12000, :referencia, :pagado_en)"
                ),
                {
                    "id": pago_id,
                    "cobro": cobro_id,
                    "referencia": "legacy-ref",
                    "pagado_en": pagado_en,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO pase "
                    "(id, placa, sede_id, vigente_desde, vigente_hasta) "
                    "VALUES (:id, 'LEG123', :sede, :desde, :hasta)"
                ),
                {
                    "id": pase_id,
                    "sede": sede_id,
                    "desde": pagado_en,
                    "hasta": datetime(2026, 3, 11, 11, 0, tzinfo=timezone.utc),
                },
            )

        migration_runner(database_url, "head")
        with engine.connect() as connection:
            payment = connection.execute(
                sa.text("SELECT id, referencia_pasarela FROM pago")
            ).one()
            legacy_pass = connection.execute(
                sa.text(
                    "SELECT id, cobro_id, dia_operativo FROM pase"
                )
            ).one()
        assert payment.id == pago_id
        assert payment.referencia_pasarela == "legacy-ref"
        assert legacy_pass.id == pase_id
        assert legacy_pass.cobro_id is None
        assert legacy_pass.dia_operativo is None
    finally:
        engine.dispose()


def test_valid_sede_vehicle_tarifa_cobro_and_pago_are_inserted(
    db_session: Session,
) -> None:
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


def test_database_unique_constraint_and_repository_conflict_handling(
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
    with db_session.begin_nested():
        assert SqlAlchemyCobroRepository(db_session).add(duplicate_entity) is False


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
    assert (
        db_session.query(Pago)
        .filter(Pago.referencia_pasarela == payment.referencia_pasarela)
        .count()
        == 1
    )


def test_payment_and_pass_are_unique_per_charge_in_postgresql(
    db_session: Session,
) -> None:
    _, _, _, cobro = _seed(db_session)
    pagado_en = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        Pago(
            cobro_id=cobro.id,
            medio="EFECTIVO",
            valor=cobro.valor,
            referencia_pasarela="pago-cobro-unico",
            pagado_en=pagado_en,
        )
    )
    db_session.add(
        Pase(
            cobro_id=cobro.id,
            dia_operativo=cobro.dia_operativo,
            placa=cobro.placa,
            sede_id=cobro.sede_id,
            vigente_desde=pagado_en,
            vigente_hasta=datetime(2026, 3, 11, 6, 0, tzinfo=timezone.utc),
        )
    )
    db_session.flush()

    with pytest.raises(IntegrityError) as payment_error:
        with db_session.begin_nested():
            db_session.add(
                Pago(
                    cobro_id=cobro.id,
                    medio="EFECTIVO",
                    valor=cobro.valor,
                    referencia_pasarela="pago-cobro-segundo",
                    pagado_en=pagado_en,
                )
            )
            db_session.flush()
    assert _check_constraint_name(payment_error.value) == "uq_pago_cobro_id"

    with pytest.raises(IntegrityError) as pass_error:
        with db_session.begin_nested():
            db_session.add(
                Pase(
                    cobro_id=cobro.id,
                    dia_operativo=cobro.dia_operativo,
                    placa=cobro.placa,
                    sede_id=cobro.sede_id,
                    vigente_desde=pagado_en,
                    vigente_hasta=datetime(2026, 3, 11, 6, 0, tzinfo=timezone.utc),
                )
            )
            db_session.flush()
    assert _check_constraint_name(pass_error.value) == "uq_pase_cobro_id"


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
        _check_constraint_name(tarifa_error.value) == "uq_tarifa_sede_tipo_franja_desde"
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
    assert "CREATE TABLE usuario" in result.stdout
    assert "uq_usuario_username" in result.stdout
    assert "CREATE TABLE configuracion_operativa" in result.stdout


def test_duplicate_usuario_is_rejected_by_database_and_repository(
    db_session: Session,
) -> None:
    hasher = Argon2PasswordHasher()
    usuario = Usuario(
        username="usuario_unico",
        password_hash=hasher.hash("secreto"),
        rol="OPERADOR",
        activo=True,
    )
    db_session.add(usuario)
    db_session.flush()

    duplicate = Usuario(
        username="usuario_unico",
        password_hash=hasher.hash("otro"),
        rol="ADMINISTRADOR",
        activo=True,
    )
    with pytest.raises(IntegrityError) as database_error:
        with db_session.begin_nested():
            db_session.add(duplicate)
            db_session.flush()
    assert _check_constraint_name(database_error.value) == "uq_usuario_username"

    duplicate_entity = UsuarioEntity(
        id=uuid4(),
        username="usuario_unico",
        password_hash=hasher.hash("otro"),
        rol=Rol.OPERADOR,
        activo=True,
    )
    with pytest.raises(UsuarioDuplicadoError) as repository_error:
        with db_session.begin_nested():
            SqlAlchemyUsuarioRepository(db_session).add(duplicate_entity)
    assert isinstance(repository_error.value.__cause__, IntegrityError)


def test_seed_users_is_idempotent(db_session: Session) -> None:
    seed_users(db_session)
    seed_users(db_session)

    usernames = (
        db_session.query(Usuario)
        .filter(Usuario.username.in_(("admin_prueba", "operador_prueba")))
        .all()
    )
    assert len(usernames) == 2


def test_development_seed_creates_operational_data_idempotently(
    db_session: Session,
) -> None:
    seed_development_data(db_session)
    seed_development_data(db_session)

    sede = db_session.query(Sede).filter_by(nombre="Sede Demo Parqueadero").one()
    assert (
        db_session.query(Carril)
        .filter(Carril.sede_id == sede.id)
        .count()
        == 2
    )
    assert (
        db_session.query(Tarifa)
        .filter(Tarifa.sede_id == sede.id)
        .count()
        == 4
    )
