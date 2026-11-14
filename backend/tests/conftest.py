import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

os.environ.setdefault("APP_NAME", "Parqueadero API")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://parqueadero:parqueadero_dev@localhost:5432/parqueadero",
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _create_database(admin_url: URL, database_name: str) -> None:
    engine = create_engine(admin_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    quoted_name = engine.dialect.identifier_preparer.quote(database_name)
    try:
        with engine.connect() as connection:
            exists = connection.exec_driver_sql(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (database_name,),
            ).scalar()
            if not exists:
                connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
    finally:
        engine.dispose()


def _drop_database(admin_url: URL, database_name: str) -> None:
    engine = create_engine(admin_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    quoted_name = engine.dialect.identifier_preparer.quote(database_name)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            connection.exec_driver_sql(f"DROP DATABASE {quoted_name}")
    finally:
        engine.dispose()


def _run_migration(database_url: URL, revision: str) -> None:
    engine = create_engine(database_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            if revision == "base":
                command.downgrade(config, revision)
            else:
                command.upgrade(config, revision)
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> Iterator[URL]:
    development_url = make_url(os.environ["DATABASE_URL"])
    if development_url.get_backend_name() != "postgresql":
        pytest.fail("Las pruebas de integración requieren PostgreSQL; SQLite no está permitido.")
    if development_url.database is None:
        pytest.fail("DATABASE_URL debe incluir el nombre de la base de desarrollo.")

    test_database_name = f"{development_url.database}_test"
    test_url = development_url.set(database=test_database_name)
    _create_database(development_url, test_database_name)
    _run_migration(test_url, "head")
    yield test_url


@pytest.fixture(scope="session")
def database_engine(database_url: URL):
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(database_engine) -> Iterator[Session]:
    connection = database_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def disposable_migration_database(database_url: URL) -> Iterator[URL]:
    base_url = make_url(os.environ["DATABASE_URL"])
    database_name = f"{base_url.database}_migration_{uuid4().hex}"
    disposable_url = base_url.set(database=database_name)
    _create_database(base_url, database_name)
    try:
        yield disposable_url
    finally:
        _drop_database(base_url, database_name)
