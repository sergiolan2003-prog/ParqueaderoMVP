from collections.abc import Iterator
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.accesos.infrastructure.models import Carril, Sede
from app.modules.auth.infrastructure.seed import seed_users
from app.modules.tarifas.infrastructure.models import Tarifa

LOCAL_ZONE = ZoneInfo("America/Bogota")
DEFAULT_CONFIGURATION = {
    "daytime_start": "07:00",
    "daytime_end": "19:00",
    "nighttime_start": "19:00",
    "nighttime_end": "07:00",
    "lpr_confidence_threshold": 0.95,
}


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    seed_users(db_session)

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _token(client: TestClient, *, administrator: bool) -> str:
    username = (
        settings.seed_admin_username
        if administrator
        else settings.seed_operador_username
    )
    password = (
        settings.seed_admin_password
        if administrator
        else settings.seed_operador_password
    )
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_operational_configuration_is_admin_only_and_defaults_to_environment(
    client: TestClient,
) -> None:
    administrator = _token(client, administrator=True)
    operator = _token(client, administrator=False)

    default = client.get(
        "/configuracion/operativa",
        headers={"Authorization": f"Bearer {administrator}"},
    )
    assert default.status_code == 200
    assert default.json() == {
        "daytime_start": settings.daytime_start.isoformat(),
        "daytime_end": settings.daytime_end.isoformat(),
        "nighttime_start": settings.nighttime_start.isoformat(),
        "nighttime_end": settings.nighttime_end.isoformat(),
        "lpr_confidence_threshold": settings.lpr_confidence_threshold,
    }

    denied = client.get(
        "/configuracion/operativa",
        headers={"Authorization": f"Bearer {operator}"},
    )
    assert denied.status_code == 403
    assert client.get("/configuracion/operativa").status_code == 401


def test_admin_can_persist_valid_schedule_and_invalid_values_are_rejected(
    client: TestClient,
) -> None:
    administrator = _token(client, administrator=True)
    headers = {"Authorization": f"Bearer {administrator}"}

    updated = client.put(
        "/configuracion/operativa",
        json=DEFAULT_CONFIGURATION,
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["daytime_start"] == "07:00:00"
    assert updated.json()["lpr_confidence_threshold"] == 0.95
    assert client.get("/configuracion/operativa", headers=headers).json() == (
        updated.json()
    )

    overlapping_schedule = client.put(
        "/configuracion/operativa",
        json={
            **DEFAULT_CONFIGURATION,
            "nighttime_start": "18:00",
        },
        headers=headers,
    )
    assert overlapping_schedule.status_code == 422
    assert "solapan" in overlapping_schedule.json()["detail"][0]["msg"]

    invalid_threshold = client.put(
        "/configuracion/operativa",
        json={**DEFAULT_CONFIGURATION, "lpr_confidence_threshold": 1.01},
        headers=headers,
    )
    assert invalid_threshold.status_code == 422

    unchanged = client.get("/configuracion/operativa", headers=headers)
    assert unchanged.json() == updated.json()


def test_saved_threshold_and_schedule_apply_to_new_vehicle_entries(
    client: TestClient,
    db_session: Session,
) -> None:
    administrator = _token(client, administrator=True)
    operator = _token(client, administrator=False)
    admin_headers = {"Authorization": f"Bearer {administrator}"}
    operator_headers = {"Authorization": f"Bearer {operator}"}

    saved = client.put(
        "/configuracion/operativa",
        json=DEFAULT_CONFIGURATION,
        headers=admin_headers,
    )
    assert saved.status_code == 200

    sede = Sede(
        nombre=f"Configuración-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(6),
        cupos_carro=20,
        cupos_moto=10,
    )
    db_session.add(sede)
    db_session.flush()
    carril = Carril(sede_id=sede.id, sentido="ENTRADA")
    db_session.add(carril)
    db_session.add_all(
        [
            Tarifa(
                sede_id=sede.id,
                tipo_vehiculo="CARRO",
                franja="DIURNA",
                valor=Decimal("12000.00"),
                vigente_desde=date(2026, 1, 1),
            ),
            Tarifa(
                sede_id=sede.id,
                tipo_vehiculo="CARRO",
                franja="NOCTURNA",
                valor=Decimal("8000.00"),
                vigente_desde=date(2026, 1, 1),
            ),
        ]
    )
    db_session.flush()

    def register_entry(confidence: float):
        return client.post(
            "/accesos/entrada",
            headers=operator_headers,
            json={
                "evento_id": str(uuid4()),
                "placa": "ABC123",
                "carril_id": str(carril.id),
                "ocurrido_en": datetime(
                    2026,
                    3,
                    10,
                    18,
                    30,
                    tzinfo=LOCAL_ZONE,
                ).isoformat(),
                "confianza_lpr": confidence,
            },
        )

    rejected = register_entry(0.9)
    assert rejected.status_code == 422
    assert "CONFIANZA_LPR_INSUFICIENTE" in rejected.json()["detail"]

    updated = client.put(
        "/configuracion/operativa",
        json={**DEFAULT_CONFIGURATION, "lpr_confidence_threshold": 0.85},
        headers=admin_headers,
    )
    assert updated.status_code == 200

    accepted = register_entry(0.9)
    assert accepted.status_code == 201
    assert accepted.json()["franja"] == "DIURNA"
    assert accepted.json()["valor"] == "12000.00"
