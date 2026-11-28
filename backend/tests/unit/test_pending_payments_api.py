from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.modules.auth.api.dependencies import get_usuario_actual
from app.modules.auth.domain.entities import IdentidadAutenticada, Rol
from app.modules.cobros.infrastructure.models import Cobro


def test_operator_can_list_pending_charges() -> None:
    charge = Cobro(
        id=uuid4(),
        placa="ABC123",
        sede_id=uuid4(),
        dia_operativo=date(2026, 3, 10),
        tarifa_id=uuid4(),
        valor=Decimal("12000.00"),
        estado="PENDIENTE",
    )
    db_mock = MagicMock()
    db_mock.execute.return_value.all.return_value = [(charge, "Sede Principal")]
    app.dependency_overrides[get_usuario_actual] = lambda: IdentidadAutenticada(
        username="operador_test",
        rol=Rol.OPERADOR,
    )
    app.dependency_overrides[get_db] = lambda: db_mock

    try:
        with TestClient(app) as client:
            response = client.get("/pagos/pendientes")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "cobro_id": str(charge.id),
            "placa": "ABC123",
            "sede_id": str(charge.sede_id),
            "sede_nombre": "Sede Principal",
            "dia_operativo": "2026-03-10",
            "valor": "12000.00",
        }
    ]


def test_pending_charges_require_authentication() -> None:
    try:
        with TestClient(app) as client:
            response = client.get("/pagos/pendientes")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
