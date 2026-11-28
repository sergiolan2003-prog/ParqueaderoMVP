from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.modules.accesos.infrastructure.models import Carril
from app.modules.auth.api.dependencies import get_usuario_actual
from app.modules.auth.domain.entities import IdentidadAutenticada, Rol


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("rol", [Rol.ADMINISTRADOR, Rol.OPERADOR])
def test_listar_carriles_muestra_id_y_sede_para_ambos_roles(
    client: TestClient,
    rol: Rol,
) -> None:
    carril = Carril(id=uuid4(), sede_id=uuid4(), sentido="ENTRADA")
    db_mock = MagicMock()
    query = db_mock.query.return_value
    query.join.return_value = query
    query.order_by.return_value.all.return_value = [(carril, "Sede Principal")]

    app.dependency_overrides[get_usuario_actual] = lambda: IdentidadAutenticada(
        username="usuario_test",
        rol=rol,
    )
    app.dependency_overrides[get_db] = lambda: db_mock

    response = client.get("/carriles/")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(carril.id),
            "sede_id": str(carril.sede_id),
            "sede_nombre": "Sede Principal",
            "sentido": "ENTRADA",
        }
    ]
