from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.modules.accesos.infrastructure.models import EventoAcceso
from app.modules.auth.api.dependencies import get_usuario_actual
from app.modules.auth.domain.entities import IdentidadAutenticada, Rol
from app.modules.cobros.infrastructure.models import Cobro


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def _override_user(rol: Rol):
    def _dep() -> IdentidadAutenticada:
        return IdentidadAutenticada(username="usuario_test", rol=rol)

    return _dep


def test_operador_recibe_acceso_denegado_en_eventos_y_cobros(
        client: TestClient,
    ) -> None:
    app.dependency_overrides[get_usuario_actual] = _override_user(Rol.OPERADOR)

    resp_eventos = client.get("/api/v1/auditoria/eventos")
    resp_cobros = client.get("/api/v1/auditoria/cobros")

    assert resp_eventos.status_code == 403
    assert resp_cobros.status_code == 403


def test_rango_fechas_invalido_devuelve_error_400(client: TestClient) -> None:
    app.dependency_overrides[get_usuario_actual] = _override_user(Rol.ADMINISTRADOR)
    app.dependency_overrides[get_db] = lambda: MagicMock()

    resp_cobros = client.get(
        "/api/v1/auditoria/cobros",
        params={"fecha_desde": "2026-11-25", "fecha_hasta": "2026-11-20"},
    )
    resp_eventos = client.get(
        "/api/v1/auditoria/eventos",
        params={
            "fecha_desde": "2026-11-25T15:00:00Z",
            "fecha_hasta": "2026-11-25T10:00:00Z",
        },
    )

    assert resp_cobros.status_code == 400
    assert "Rango de fechas inválido" in resp_cobros.json()["detail"]
    assert resp_eventos.status_code == 400
    assert "Rango de fechas inválido" in resp_eventos.json()["detail"]


def test_listar_cobros_con_filtros_y_paginacion(client: TestClient) -> None:
    app.dependency_overrides[get_usuario_actual] = _override_user(Rol.ADMINISTRADOR)

    cobro_mock = Cobro(
        id=uuid4(),
        placa="ABC123",
        sede_id=uuid4(),
        dia_operativo=date(2026, 11, 25),
        tarifa_id=uuid4(),
        valor=Decimal("5000.00"),
        estado="PENDIENTE",
    )

    db_mock = MagicMock()
    query_mock = db_mock.query.return_value
    query_mock.filter.return_value = query_mock
    query_mock.with_entities.return_value.scalar.return_value = 1
    paginated = query_mock.order_by.return_value.offset.return_value.limit.return_value
    paginated.all.return_value = [cobro_mock]
    app.dependency_overrides[get_db] = lambda: db_mock

    resp = client.get(
        "/api/v1/auditoria/cobros",
        params={"placa": "abc123", "estado": "PENDIENTE", "page": 1, "page_size": 10},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert len(body["items"]) == 1
    assert body["items"][0]["placa"] == "ABC123"
    assert body["items"][0]["estado"] == "PENDIENTE"


def test_listar_eventos_distingue_lectura_manual(client: TestClient) -> None:
    app.dependency_overrides[get_usuario_actual] = _override_user(Rol.ADMINISTRADOR)

    evento_mock = EventoAcceso(
        id=uuid4(),
        placa="XYZ987",
        carril_id=uuid4(),
        ocurrido_en=datetime(2026, 11, 25, 14, 0, tzinfo=UTC),
        confianza_lpr=0.45,
        lectura_manual=True,
        foto_url=None,
    )

    db_mock = MagicMock()
    query_mock = db_mock.query.return_value.join.return_value
    query_mock.filter.return_value = query_mock
    query_mock.with_entities.return_value.scalar.return_value = 1
    paginated = query_mock.order_by.return_value.offset.return_value.limit.return_value
    paginated.all.return_value = [(evento_mock, "ENTRADA")]
    app.dependency_overrides[get_db] = lambda: db_mock

    resp = client.get(
        "/api/v1/auditoria/eventos",
        params={"placa": "XYZ987", "lectura_manual": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["lectura_manual"] is True
    assert body["items"][0]["sentido"] == "ENTRADA"