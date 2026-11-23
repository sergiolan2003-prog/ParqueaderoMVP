from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.accesos.application.entry import RegistrarEntradaUseCase
from app.modules.accesos.infrastructure.models import (
    Carril,
    EventoAcceso,
    Sede,
    Vehiculo,
)
from app.modules.auth.infrastructure.seed import seed_users
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.pases.infrastructure.models import Pase
from app.modules.tarifas.infrastructure.models import Tarifa

LOCAL_ZONE = ZoneInfo("America/Bogota")


@pytest.fixture
def operator_client(db_session: Session) -> Iterator[tuple[TestClient, dict[str, str]]]:
    seed_users(db_session)

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            data={
                "username": settings.seed_operador_username,
                "password": settings.seed_operador_password,
            },
        )
        assert login.status_code == 200
        yield client, {"Authorization": f"Bearer {login.json()['access_token']}"}
    app.dependency_overrides.clear()


def _new_sede(session: Session, name: str) -> tuple[Sede, Carril]:
    sede = Sede(
        nombre=f"{name}-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(6),
        cupos_carro=50,
        cupos_moto=50,
    )
    session.add(sede)
    session.flush()
    carril = Carril(sede_id=sede.id, sentido="ENTRADA")
    session.add(carril)
    session.flush()
    return sede, carril


def _add_tarifa(
    session: Session,
    sede: Sede,
    tipo_vehiculo: str,
    franja: str,
    valor: Decimal,
) -> Tarifa:
    tarifa = Tarifa(
        sede_id=sede.id,
        tipo_vehiculo=tipo_vehiculo,
        franja=franja,
        valor=valor,
        vigente_desde=date(2026, 1, 1),
    )
    session.add(tarifa)
    session.flush()
    return tarifa


def _add_standard_tariffs(session: Session, sede: Sede) -> dict[str, Tarifa]:
    tarifas = {
        "day": _add_tarifa(
            session, sede, "CARRO", "DIURNA", Decimal("12000.00")
        ),
        "night": _add_tarifa(
            session, sede, "CARRO", "NOCTURNA", Decimal("8000.00")
        ),
        "moto_day": _add_tarifa(
            session, sede, "MOTO", "DIURNA", Decimal("0.00")
        ),
        "moto_night": _add_tarifa(
            session, sede, "MOTO", "NOCTURNA", Decimal("0.00")
        ),
    }
    return tarifas


def _entry(
    client: TestClient,
    headers: dict[str, str],
    lane: Carril,
    plate: str,
    when: datetime,
    event_id: UUID | None = None,
) -> object:
    event_id = event_id or uuid4()
    return client.post(
        "/accesos/entrada",
        headers=headers,
        json={
            "evento_id": str(event_id),
            "placa": plate,
            "carril_id": str(lane.id),
            "ocurrido_en": when.isoformat(),
            "confianza_lpr": 0.99,
        },
    )


@pytest.mark.parametrize(
    ("hour", "minute", "expected_period", "expected_value"),
    [
        (8, 0, "DIURNA", Decimal("12000.00")),
        (19, 0, "NOCTURNA", Decimal("8000.00")),
    ],
)
def test_car_entry_creates_pending_charge_at_first_entry_rate(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
    hour: int,
    minute: int,
    expected_period: str,
    expected_value: Decimal,
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Ingreso")
    tariffs = _add_standard_tariffs(db_session, sede)
    event_id = uuid4()
    response = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, hour, minute, tzinfo=LOCAL_ZONE),
        event_id,
    )

    assert response.status_code == 201
    result = response.json()
    assert result["evento_id"] == str(event_id)
    assert db_session.get(EventoAcceso, event_id) is not None
    assert result["franja"] == expected_period
    assert result["cobro_creado"] is True, result
    assert Decimal(result["valor"]) == expected_value
    expected_tarifa = tariffs["day" if expected_period == "DIURNA" else "night"]
    assert result["tarifa_id"] == str(expected_tarifa.id)
    assert result["dia_operativo"] == "2026-03-10"
    assert db_session.get(Cobro, UUID(result["cobro_id"])).estado == "PENDIENTE"


def test_motor_configured_zero_for_motorcycle_does_not_create_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Moto")
    tariffs = _add_standard_tariffs(db_session, sede)

    response = _entry(
        client,
        headers,
        lane,
        "ABC12D",
        datetime(2026, 3, 10, 10, 0, tzinfo=LOCAL_ZONE),
    )

    assert response.status_code == 201
    assert response.json()["cobro_creado"] is False
    assert response.json()["tarifa_id"] == str(tariffs["moto_day"].id)
    assert Decimal(response.json()["valor"]) == Decimal("0.00")
    assert db_session.query(Cobro).filter(Cobro.sede_id == sede.id).count() == 0


def test_current_pass_prevents_charge_on_reentry(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Pase")
    vehicle = Vehiculo(placa="ABC123", tipo="CARRO")
    db_session.add(vehicle)
    db_session.flush()
    db_session.add(
        Pase(
            placa=vehicle.placa,
            sede_id=sede.id,
            vigente_desde=datetime(2026, 3, 10, 20, 0, tzinfo=LOCAL_ZONE),
            vigente_hasta=datetime(2026, 3, 10, 23, 0, tzinfo=LOCAL_ZONE),
        )
    )
    db_session.flush()

    response = _entry(
        client,
        headers,
        lane,
        vehicle.placa,
        datetime(2026, 3, 10, 22, 0, tzinfo=LOCAL_ZONE),
    )

    assert response.status_code == 201
    assert response.json()["pase_vigente"] is True
    assert response.json()["cobro_creado"] is False
    assert db_session.query(Cobro).filter(Cobro.sede_id == sede.id).count() == 0
    assert db_session.query(Tarifa).filter(Tarifa.sede_id == sede.id).count() == 0


def test_new_operating_day_after_0550_creates_a_new_daytime_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "CambioDia")
    tarifas = _add_standard_tariffs(db_session, sede)

    previous_day = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 5, 50, tzinfo=LOCAL_ZONE),
    )
    next_day = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 9, 0, tzinfo=LOCAL_ZONE),
    )

    assert previous_day.status_code == 201
    assert previous_day.json()["dia_operativo"] == "2026-03-09"
    assert previous_day.json()["franja"] == "NOCTURNA"
    assert next_day.status_code == 201
    assert next_day.json()["dia_operativo"] == "2026-03-10"
    assert next_day.json()["franja"] == "DIURNA"
    assert next_day.json()["cobro_creado"] is True, next_day.json()
    assert next_day.json()["tarifa_id"] == str(tarifas["day"].id)
    assert Decimal(next_day.json()["valor"]) == Decimal("12000.00")
    assert next_day.json()["cobro_id"] != previous_day.json()["cobro_id"]
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == "ABC123", Cobro.sede_id == sede.id)
        .count()
        == 2
    )


def test_missing_tariff_rejects_entry_without_zero_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "SinTarifa")

    response = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE),
    )

    assert response.status_code == 409
    assert "No hay tarifa vigente configurada" in response.json()["detail"]
    assert db_session.query(Cobro).filter(Cobro.sede_id == sede.id).count() == 0


def test_reentry_without_pass_reuses_same_operating_day_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Reingreso")
    _add_standard_tariffs(db_session, sede)
    first = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE),
    )
    second = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 22, 0, tzinfo=LOCAL_ZONE),
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["cobro_creado"] is True, first.json()
    assert second.json()["cobro_creado"] is False
    assert second.json()["cobro_id"] == first.json()["cobro_id"]
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == "ABC123", Cobro.sede_id == sede.id)
        .count()
        == 1
    )


def test_concurrent_charge_inserts_leave_one_charge(
    database_engine,
) -> None:
    sessions = sessionmaker(bind=database_engine)
    random_value = uuid4().int
    letras = "".join(
        chr(ord("A") + ((random_value >> (position * 5)) % 26))
        for position in range(3)
    )
    placa = f"{letras}{random_value % 1000:03d}"
    sede_id = uuid4()
    carril_id = uuid4()
    instante = datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE)

    with sessions.begin() as session:
        sede = Sede(
            id=sede_id,
            nombre=f"Concurrente-{uuid4()}",
            zona_horaria="America/Bogota",
            inicio_dia_operativo=time(6),
            cupos_carro=10,
            cupos_moto=10,
        )
        carril = Carril(
            id=carril_id,
            sede_id=sede_id,
            sentido="ENTRADA",
        )
        tarifa = Tarifa(
            sede_id=sede_id,
            tipo_vehiculo="CARRO",
            franja="DIURNA",
            valor=Decimal("12000.00"),
            vigente_desde=date(2026, 1, 1),
        )
        session.add(sede)
        session.flush()
        session.add_all([carril, tarifa])

    barrier = Barrier(2)

    def register_entry() -> bool:
        with sessions() as session:
            barrier.wait(timeout=10)
            result = RegistrarEntradaUseCase(session).ejecutar(
                evento_id=uuid4(),
                placa=placa,
                carril_id=carril_id,
                ocurrido_en=instante,
            )
            return result.cobro_creado

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: register_entry(), range(2)))

    with sessions() as session:
        charge_count = (
            session.query(func.count(Cobro.id))
            .filter(
                Cobro.placa == placa,
                Cobro.sede_id == sede_id,
                Cobro.dia_operativo == date(2026, 3, 10),
            )
            .scalar()
        )
        event_count = (
            session.query(func.count(EventoAcceso.id))
            .filter(EventoAcceso.placa == placa)
            .scalar()
        )

    assert sorted(results) == [False, True]
    assert charge_count == 1
    assert event_count == 2
