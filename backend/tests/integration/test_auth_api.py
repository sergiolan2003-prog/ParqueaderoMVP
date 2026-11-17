from collections.abc import Iterator
from datetime import UTC, datetime

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.auth.infrastructure.seed import seed_users


@pytest.fixture
def auth_client(db_session: Session) -> Iterator[TestClient]:
    seed_users(db_session)

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _login(client: TestClient, username: str, password: str):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )


def test_admin_login_and_admin_route(auth_client: TestClient) -> None:
    login = _login(
        auth_client,
        settings.seed_admin_username,
        settings.seed_admin_password,
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = auth_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["rol"] == "ADMINISTRADOR"

    admin = auth_client.get(
        "/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert admin.status_code == 200


def test_operator_denied_on_admin_route(auth_client: TestClient) -> None:
    login = _login(
        auth_client,
        settings.seed_operador_username,
        settings.seed_operador_password,
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = auth_client.get(
        "/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "username,password",
    [
        ("admin_prueba", "incorrecta"),
        ("inexistente", "incorrecta"),
    ],
)
def test_bad_credentials_return_401(
    auth_client: TestClient,
    username: str,
    password: str,
) -> None:
    response = _login(auth_client, username, password)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_missing_invalid_and_expired_tokens_return_401(
    auth_client: TestClient,
) -> None:
    missing = auth_client.get("/auth/me")
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"

    invalid = auth_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer alterado"},
    )
    assert invalid.status_code == 401
    assert invalid.headers["www-authenticate"] == "Bearer"

    expired = jwt.encode(
        {
            "sub": settings.seed_admin_username,
            "rol": "ADMINISTRADOR",
            "iat": int(datetime(2020, 1, 1, tzinfo=UTC).timestamp()),
            "exp": int(datetime(2020, 1, 2, tzinfo=UTC).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    expired_response = auth_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_response.status_code == 401
    assert expired_response.headers["www-authenticate"] == "Bearer"
