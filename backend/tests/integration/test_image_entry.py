from collections.abc import Iterator
from datetime import date, time
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.accesos.infrastructure.models import Carril, Sede
from app.modules.auth.infrastructure.seed import seed_users
from app.modules.tarifas.infrastructure.models import Tarifa


@pytest.fixture
def image_entry_client(db_session) -> Iterator[tuple[TestClient, str, dict[str, str]]]:
    seed_users(db_session)
    sede = Sede(
        nombre=f"Imagen-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(6),
        cupos_carro=20,
        cupos_moto=10,
    )
    db_session.add(sede)
    db_session.flush()
    carril = Carril(sede_id=sede.id, sentido="ENTRADA")
    db_session.add(carril)
    tarifa = Tarifa(
        sede_id=sede.id,
        tipo_vehiculo="CARRO",
        franja="DIURNA",
        valor=Decimal("12000.00"),
        vigente_desde=date(2026, 1, 1),
    )
    db_session.add(tarifa)
    nocturna = Tarifa(
        sede_id=sede.id,
        tipo_vehiculo="CARRO",
        franja="NOCTURNA",
        valor=Decimal("8000.00"),
        vigente_desde=date(2026, 1, 1),
    )
    db_session.add(nocturna)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            login = client.post(
                "/auth/login",
                data={
                    "username": settings.seed_operador_username,
                    "password": settings.seed_operador_password,
                },
            )
            assert login.status_code == 200
            yield (
                client,
                str(carril.id),
                {"Authorization": f"Bearer {login.json()['access_token']}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)


def _jpeg() -> BytesIO:
    return BytesIO(b"\xff\xd8\xffHU27-imagen-simulada")


def test_image_entry_registers_plate_with_photo_url(
    image_entry_client,
) -> None:
    client, carril_id, headers = image_entry_client
    response = client.post(
        "/accesos/entrada/imagen",
        headers=headers,
        data={"carril_id": carril_id},
        files={"imagen": ("ABC123_0.92.jpg", _jpeg(), "image/jpeg")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["placa"] == "ABC123"
    assert body["confianza_lpr"] == 0.92
    assert body["foto_url"].endswith(".jpg")


def test_image_entry_low_confidence_requires_manual(
    image_entry_client,
) -> None:
    client, carril_id, headers = image_entry_client
    response = client.post(
        "/accesos/entrada/imagen",
        headers=headers,
        data={"carril_id": carril_id},
        files={"imagen": ("ABC123_0.40.jpg", _jpeg(), "image/jpeg")},
    )

    assert response.status_code == 422
    assert "CONFIANZA_LPR_INSUFICIENTE" in response.text


def test_image_entry_rejects_invalid_name_without_record(
    image_entry_client,
) -> None:
    client, carril_id, headers = image_entry_client
    response = client.post(
        "/accesos/entrada/imagen",
        headers=headers,
        data={"carril_id": carril_id},
        files={"imagen": ("sin-formato.jpg", _jpeg(), "image/jpeg")},
    )

    assert response.status_code == 422


def test_image_entry_rejects_invalid_plate(
    image_entry_client,
) -> None:
    client, carril_id, headers = image_entry_client
    response = client.post(
        "/accesos/entrada/imagen",
        headers=headers,
        data={"carril_id": carril_id},
        files={"imagen": ("AB1234_0.92.jpg", _jpeg(), "image/jpeg")},
    )

    assert response.status_code == 422


def test_image_entry_rejects_non_image(
    image_entry_client,
) -> None:
    client, carril_id, headers = image_entry_client
    response = client.post(
        "/accesos/entrada/imagen",
        headers=headers,
        data={"carril_id": carril_id},
        files={"imagen": ("ABC123_0.92.jpg", BytesIO(b"texto"), "text/plain")},
    )

    assert response.status_code == 422


def test_image_entry_rejects_oversized_image(
    image_entry_client,
) -> None:
    client, carril_id, headers = image_entry_client
    response = client.post(
        "/accesos/entrada/imagen",
        headers=headers,
        data={"carril_id": carril_id},
        files={
            "imagen": (
                "ABC123_0.92.jpg",
                BytesIO(b"\xff\xd8\xff" + b"x" * (settings.lpr_image_max_bytes + 1)),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 413
