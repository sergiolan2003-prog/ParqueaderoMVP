from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.accesos.application.services import ValidarSalidaVehiculoUseCase
from app.modules.accesos.infrastructure.models import Carril, Sede, Vehiculo
from app.modules.auth.infrastructure.seed import seed_users
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.tarifas.application.schemas import TarifaCreate
from app.modules.tarifas.application.services import crear_o_actualizar_tarifa
from app.modules.tarifas.infrastructure.models import Tarifa


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    seed_users(db_session)

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _token(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _new_sede(name: str) -> Sede:
    return Sede(
        nombre=f"{name}-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(6),
        cupos_carro=20,
        cupos_moto=10,
    )


def _add_cobro(
    session: Session,
    *,
    placa: str,
    sede: Sede,
    dia_operativo: date,
) -> None:
    tarifa = Tarifa(
        sede_id=sede.id,
        tipo_vehiculo="CARRO",
        franja="DIURNA",
        valor=Decimal("12000.00"),
        vigente_desde=date(2026, 1, 1),
    )
    session.add(tarifa)
    session.flush()
    session.add(
        Cobro(
            placa=placa,
            sede_id=sede.id,
            dia_operativo=dia_operativo,
            tarifa_id=tarifa.id,
            valor=tarifa.valor,
            estado="PENDIENTE",
        )
    )
    session.flush()


def test_exit_ignores_debts_from_other_operating_days_and_sites(
    db_session: Session,
) -> None:
    now = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    sede = _new_sede("Salida")
    otra_sede = _new_sede("Otra")
    db_session.add_all([sede, otra_sede])
    db_session.flush()
    carril = Carril(sede_id=sede.id, sentido="SALIDA")
    vehiculo = Vehiculo(placa="ABC123", tipo="CARRO")
    db_session.add_all([carril, vehiculo])
    db_session.flush()
    _add_cobro(
        db_session,
        placa=vehiculo.placa,
        sede=sede,
        dia_operativo=date(2026, 3, 9),
    )
    _add_cobro(
        db_session,
        placa=vehiculo.placa,
        sede=otra_sede,
        dia_operativo=date(2026, 3, 10),
    )

    result = ValidarSalidaVehiculoUseCase(
        db_session,
        clock=FixedClock(now),
    ).ejecutar(vehiculo.placa, carril.id)

    assert result["barrera_abre"] is True
    assert result["registrado_en"].tzinfo is not None


def test_exit_blocks_debt_for_current_site_and_operating_day(
    db_session: Session,
) -> None:
    now = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    sede = _new_sede("Salida")
    db_session.add(sede)
    db_session.flush()
    carril = Carril(sede_id=sede.id, sentido="SALIDA")
    vehiculo = Vehiculo(placa="DEF456", tipo="CARRO")
    db_session.add_all([carril, vehiculo])
    db_session.flush()
    _add_cobro(
        db_session,
        placa=vehiculo.placa,
        sede=sede,
        dia_operativo=date(2026, 3, 10),
    )

    result = ValidarSalidaVehiculoUseCase(
        db_session,
        clock=FixedClock(now),
    ).ejecutar(vehiculo.placa, carril.id)

    assert result["barrera_abre"] is False


def test_exit_rejects_vehicle_missing_from_registry(db_session: Session) -> None:
    sede = _new_sede("Salida")
    db_session.add(sede)
    db_session.flush()
    carril = Carril(sede_id=sede.id, sentido="SALIDA")
    db_session.add(carril)
    db_session.flush()

    with pytest.raises(HTTPException) as error:
        ValidarSalidaVehiculoUseCase(db_session).ejecutar("ZZZ999", carril.id)

    assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("franja", "valor", "franja_opuesta", "valor_opuesto"),
    [
        ("DIURNA", Decimal("10000.00"), "NOCTURNA", Decimal("10000.00")),
        ("NOCTURNA", Decimal("10000.00"), "DIURNA", Decimal("10000.00")),
    ],
)
def test_tariff_rn02_requires_day_rate_strictly_above_night_rate(
    db_session: Session,
    franja: str,
    valor: Decimal,
    franja_opuesta: str,
    valor_opuesto: Decimal,
) -> None:
    sede = _new_sede("Tarifas")
    db_session.add(sede)
    db_session.flush()
    db_session.add(
        Tarifa(
            sede_id=sede.id,
            tipo_vehiculo="CARRO",
            franja=franja_opuesta,
            valor=valor_opuesto,
            vigente_desde=date(2026, 1, 1),
        )
    )
    db_session.flush()
    tarifa = TarifaCreate(
        sede_id=sede.id,
        tipo_vehiculo="CARRO",
        franja=franja,
        valor=valor,
        vigente_desde=date(2026, 3, 10),
    )

    with pytest.raises(HTTPException) as error:
        crear_o_actualizar_tarifa(db_session, tarifa)

    assert error.value.status_code == 400


def test_exit_endpoint_requires_operator_and_validates_plate_format(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede("Salida")
    db_session.add(sede)
    db_session.flush()
    carril = Carril(sede_id=sede.id, sentido="SALIDA")
    vehiculo = Vehiculo(placa="ABC123", tipo="CARRO")
    db_session.add_all([carril, vehiculo])
    db_session.flush()
    payload = {"placa": " abc123 ", "carril_id": str(carril.id)}

    unauthenticated = client.post("/accesos/salida", json=payload)
    assert unauthenticated.status_code == 401

    token = _token(
        client,
        settings.seed_operador_username,
        settings.seed_operador_password,
    )
    headers = {"Authorization": f"Bearer {token}"}

    invalid_plate = client.post(
        "/accesos/salida",
        json={**payload, "placa": "ABC1234"},
        headers=headers,
    )
    assert invalid_plate.status_code == 422

    response = client.post("/accesos/salida", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["placa"] == "ABC123"


def test_tariff_endpoint_is_admin_only_and_validates_inputs(
    client: TestClient,
    db_session: Session,
) -> None:
    sede = _new_sede("Tarifas")
    db_session.add(sede)
    db_session.flush()
    payload = {
        "sede_id": str(sede.id),
        "tipo_vehiculo": "carro",
        "franja": "diurna",
        "valor": "12000.00",
        "vigente_desde": "2026-03-10",
        "vigente_hasta": None,
    }

    unauthenticated = client.post("/tarifas/", json=payload)
    assert unauthenticated.status_code == 401

    operator_token = _token(
        client,
        settings.seed_operador_username,
        settings.seed_operador_password,
    )
    operator_response = client.post(
        "/tarifas/",
        json=payload,
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert operator_response.status_code == 403

    admin_token = _token(
        client,
        settings.seed_admin_username,
        settings.seed_admin_password,
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    invalid_type = client.post(
        "/tarifas/",
        json={**payload, "tipo_vehiculo": "CAMION"},
        headers=admin_headers,
    )
    assert invalid_type.status_code == 422

    invalid_dates = client.post(
        "/tarifas/",
        json={**payload, "vigente_hasta": "2026-03-09"},
        headers=admin_headers,
    )
    assert invalid_dates.status_code == 422

    response = client.post("/tarifas/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["tipo_vehiculo"] == "CARRO"
    tarifa_anterior_id = response.json()["id"]

    nueva_vigencia = client.post(
        "/tarifas/",
        json={**payload, "vigente_desde": "2026-03-11"},
        headers=admin_headers,
    )
    assert nueva_vigencia.status_code == 201
    assert nueva_vigencia.json()["vigente_desde"] == "2026-03-11"
    assert db_session.get(Tarifa, tarifa_anterior_id).vigente_hasta == date(2026, 3, 10)

    mismo_inicio = client.post(
        "/tarifas/",
        json={**payload, "vigente_desde": "2026-03-11"},
        headers=admin_headers,
    )
    assert mismo_inicio.status_code == 409
