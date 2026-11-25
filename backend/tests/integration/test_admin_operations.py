from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.accesos.infrastructure.models import (
    Carril,
    EventoAcceso,
    Sede,
    Vehiculo,
)
from app.modules.auth.infrastructure.seed import seed_users
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.tarifas.infrastructure.models import Tarifa


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
    if administrator:
        username = settings.seed_admin_username
        password = settings.seed_admin_password
    else:
        username = settings.seed_operador_username
        password = settings.seed_operador_password
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _new_sede(name: str = "Administración") -> Sede:
    return Sede(
        nombre=f"{name}-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(6),
        cupos_carro=20,
        cupos_moto=10,
    )


def _add_tarifa(
    db_session: Session,
    *,
    sede: Sede,
    tipo_vehiculo: str,
    franja: str,
    valor: Decimal,
    vigente_desde: date,
    vigente_hasta: date | None = None,
) -> Tarifa:
    tarifa = Tarifa(
        sede_id=sede.id,
        tipo_vehiculo=tipo_vehiculo,
        franja=franja,
        valor=valor,
        vigente_desde=vigente_desde,
        vigente_hasta=vigente_hasta,
    )
    db_session.add(tarifa)
    db_session.flush()
    return tarifa


def test_admin_tariff_list_filters_and_keeps_version_history(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede()
    db_session.add(sede)
    db_session.flush()
    antigua = _add_tarifa(
        db_session,
        sede=sede,
        tipo_vehiculo="CARRO",
        franja="DIURNA",
        valor=Decimal("15000"),
        vigente_desde=date(2026, 3, 1),
        vigente_hasta=date(2026, 3, 9),
    )
    actual = _add_tarifa(
        db_session,
        sede=sede,
        tipo_vehiculo="CARRO",
        franja="DIURNA",
        valor=Decimal("16000"),
        vigente_desde=date(2026, 3, 10),
    )
    _add_tarifa(
        db_session,
        sede=sede,
        tipo_vehiculo="CARRO",
        franja="NOCTURNA",
        valor=Decimal("9000"),
        vigente_desde=date(2026, 3, 1),
    )
    token = _token(client, administrator=True)

    response = client.get(
        "/tarifas/",
        params={
            "sede_id": str(sede.id),
            "tipo_vehiculo": "CARRO",
            "franja": "DIURNA",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        str(actual.id),
        str(antigua.id),
    ]
    assert response.json()[0]["vigente_hasta"] is None
    assert response.json()[1]["vigente_hasta"] == "2026-03-09"


def test_admin_tariff_create_applies_rn02_and_versions_rn07(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede()
    db_session.add(sede)
    db_session.flush()
    token = _token(client, administrator=True)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "sede_id": str(sede.id),
        "tipo_vehiculo": "CARRO",
        "franja": "DIURNA",
        "valor": "12000",
        "vigente_desde": "2026-03-10",
    }

    day_rate = client.post("/tarifas/", json=payload, headers=headers)
    assert day_rate.status_code == 201

    invalid_night_rate = client.post(
        "/tarifas/",
        json={
            **payload,
            "franja": "NOCTURNA",
            "valor": "12000",
        },
        headers=headers,
    )
    assert invalid_night_rate.status_code == 400
    assert "RN-02" in invalid_night_rate.json()["detail"]

    night_rate = client.post(
        "/tarifas/",
        json={
            **payload,
            "franja": "NOCTURNA",
            "valor": "10000",
        },
        headers=headers,
    )
    assert night_rate.status_code == 201

    revised_night_rate = client.post(
        "/tarifas/",
        json={
            **payload,
            "franja": "NOCTURNA",
            "valor": "9000",
            "vigente_desde": "2026-03-11",
        },
        headers=headers,
    )
    assert revised_night_rate.status_code == 201
    previous_id = night_rate.json()["id"]
    previous = db_session.get(Tarifa, previous_id)
    assert previous is not None
    assert previous.vigente_hasta == date(2026, 3, 10)


def test_admin_can_list_and_update_site_capacities(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede()
    db_session.add(sede)
    db_session.flush()
    token = _token(client, administrator=True)
    headers = {"Authorization": f"Bearer {token}"}

    sedes = client.get("/sedes/", headers=headers)
    assert sedes.status_code == 200
    assert any(item["id"] == str(sede.id) for item in sedes.json())

    current = client.get(f"/sedes/{sede.id}/cupos", headers=headers)
    assert current.status_code == 200
    assert current.json()["cupos_carro"] == 20

    updated = client.put(
        f"/sedes/{sede.id}/cupos",
        json={"cupos_carro": 35, "cupos_moto": 15},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["cupos_carro"] == 35
    assert updated.json()["cupos_moto"] == 15
    assert sede.cupos_carro == 35
    assert sede.cupos_moto == 15


def test_capacity_update_rejects_negative_values_and_unknown_site(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede()
    db_session.add(sede)
    db_session.flush()
    token = _token(client, administrator=True)
    headers = {"Authorization": f"Bearer {token}"}

    negative = client.put(
        f"/sedes/{sede.id}/cupos",
        json={"cupos_carro": -1, "cupos_moto": 0},
        headers=headers,
    )
    assert negative.status_code == 422

    missing = client.get(f"/sedes/{uuid4()}/cupos", headers=headers)
    assert missing.status_code == 404


def test_access_event_consultation_normalizes_plate_filters_dates_and_paginates(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede()
    db_session.add(sede)
    db_session.flush()
    carril = Carril(sede_id=sede.id, sentido="ENTRADA")
    db_session.add_all(
        [
            carril,
            Vehiculo(placa="ABC123", tipo="CARRO"),
            Vehiculo(placa="DEF456", tipo="CARRO"),
        ]
    )
    db_session.flush()
    first_event = EventoAcceso(
        id=uuid4(),
        placa="ABC123",
        carril_id=carril.id,
        ocurrido_en=datetime(2026, 3, 10, 14, 0, tzinfo=UTC),
        confianza_lpr=0.99,
        lectura_manual=False,
    )
    second_event = EventoAcceso(
        id=uuid4(),
        placa="ABC123",
        carril_id=carril.id,
        ocurrido_en=datetime(2026, 3, 10, 15, 0, tzinfo=UTC),
        confianza_lpr=0.95,
        lectura_manual=True,
    )
    db_session.add_all([first_event, second_event])
    db_session.flush()
    token = _token(client, administrator=True)
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "placa": "abc123",
        "desde": "2026-03-10",
        "hasta": "2026-03-10",
        "page_size": 1,
    }

    first_page = client.get(
        "/consultas/eventos",
        params={**params, "page": 1},
        headers=headers,
    )
    second_page = client.get(
        "/consultas/eventos",
        params={**params, "page": 2},
        headers=headers,
    )

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 2
    assert first_page.json()["total_pages"] == 2
    assert len(first_page.json()["items"]) == 1
    assert len(second_page.json()["items"]) == 1
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]


def test_charge_consultation_filters_plate_dates_and_state(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede()
    db_session.add(sede)
    db_session.flush()
    db_session.add_all(
        [
            Vehiculo(placa="ABC123", tipo="CARRO"),
            Vehiculo(placa="DEF456", tipo="CARRO"),
        ]
    )
    tarifa = _add_tarifa(
        db_session,
        sede=sede,
        tipo_vehiculo="CARRO",
        franja="DIURNA",
        valor=Decimal("12000"),
        vigente_desde=date(2026, 1, 1),
    )
    db_session.add_all(
        [
            Cobro(
                placa="ABC123",
                sede_id=sede.id,
                dia_operativo=date(2026, 3, 10),
                tarifa_id=tarifa.id,
                valor=Decimal("12000"),
                estado="PENDIENTE",
            ),
            Cobro(
                placa="ABC123",
                sede_id=sede.id,
                dia_operativo=date(2026, 3, 11),
                tarifa_id=tarifa.id,
                valor=Decimal("12000"),
                estado="PAGADO",
            ),
            Cobro(
                placa="DEF456",
                sede_id=sede.id,
                dia_operativo=date(2026, 3, 10),
                tarifa_id=tarifa.id,
                valor=Decimal("12000"),
                estado="PENDIENTE",
            ),
        ]
    )
    db_session.flush()
    token = _token(client, administrator=True)

    response = client.get(
        "/consultas/cobros",
        params={
            "placa": "abc123",
            "desde": "2026-03-10",
            "hasta": "2026-03-10",
            "estado": "PENDIENTE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["placa"] == "ABC123"
    assert response.json()["items"][0]["estado"] == "PENDIENTE"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/tarifas/", None),
        ("get", "/sedes/", None),
        ("get", f"/sedes/{uuid4()}/cupos", None),
        ("put", f"/sedes/{uuid4()}/cupos", {"cupos_carro": 1, "cupos_moto": 1}),
        ("get", "/consultas/eventos", None),
        ("get", "/consultas/cobros", None),
    ],
)
def test_admin_routes_require_authentication_and_admin_role(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, int] | None,
) -> None:
    request = getattr(client, method)
    unauthenticated = request(path, json=payload) if payload else request(path)
    assert unauthenticated.status_code == 401

    operator_token = _token(client, administrator=False)
    operator_response = (
        request(
            path,
            json=payload,
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        if payload
        else request(
            path,
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    )
    assert operator_response.status_code == 403


def test_consultations_reject_invalid_date_ranges_and_page_sizes(
    client: TestClient,
) -> None:
    token = _token(client, administrator=True)
    headers = {"Authorization": f"Bearer {token}"}

    invalid_range = client.get(
        "/consultas/eventos",
        params={"desde": "2026-03-11", "hasta": "2026-03-10"},
        headers=headers,
    )
    assert invalid_range.status_code == 422

    invalid_page_size = client.get(
        "/consultas/cobros",
        params={"page_size": 101},
        headers=headers,
    )
    assert invalid_page_size.status_code == 422
