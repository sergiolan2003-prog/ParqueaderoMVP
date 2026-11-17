from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.clock import FixedClock
from app.modules.auth.application.services import AutenticarUsuario
from app.modules.auth.domain.entities import Rol, Usuario
from app.modules.auth.domain.exceptions import (
    CredencialesInvalidasError,
    TokenExpiradoError,
)
from app.modules.auth.infrastructure.passwords import Argon2PasswordHasher
from app.modules.auth.infrastructure.tokens import PyJwtTokenService


class InMemoryUsuarioRepository:
    def __init__(self, usuarios: list[Usuario]) -> None:
        self._usuarios = {usuario.username: usuario for usuario in usuarios}

    def obtener_por_username(self, username: str) -> Usuario | None:
        return self._usuarios.get(username)

    def add(self, usuario: Usuario) -> None:
        self._usuarios[usuario.username] = usuario


def test_password_hash_is_different_and_verifies() -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash("secreto")

    assert password_hash != "secreto"
    assert hasher.verify(password_hash, "secreto")
    assert not hasher.verify(password_hash, "incorrecta")


def test_token_roundtrip_and_fixed_clock_expiration() -> None:
    clock = FixedClock(datetime(2026, 1, 1, 12, tzinfo=UTC))
    token_service = PyJwtTokenService(clock)
    token = token_service.emitir("operador", "OPERADOR")

    assert token_service.validar(token) == ("operador", "OPERADOR")


def test_token_expiration_at_fixed_clock() -> None:
    clock = FixedClock(datetime(2026, 1, 1, 12, tzinfo=UTC))
    token = PyJwtTokenService(clock).emitir("operador", "OPERADOR")
    later = FixedClock(datetime(2026, 1, 1, 13, tzinfo=UTC))

    with pytest.raises(TokenExpiradoError):
        PyJwtTokenService(later).validar(token)


def test_invalid_signature_and_format_are_rejected() -> None:
    clock = FixedClock(datetime(2026, 1, 1, 12, tzinfo=UTC))
    service = PyJwtTokenService(clock)
    token = service.emitir("admin", "ADMINISTRADOR")

    with pytest.raises(Exception):
        service.validar(f"{token}alterado")
    with pytest.raises(Exception):
        service.validar("no-es-un-jwt")


@pytest.fixture
def authentication_case() -> tuple[AutenticarUsuario, InMemoryUsuarioRepository]:
    hasher = Argon2PasswordHasher()
    usuario = Usuario(
        id=uuid4(),
        username="operador",
        password_hash=hasher.hash("correcta"),
        rol=Rol.OPERADOR,
        activo=True,
    )
    repository = InMemoryUsuarioRepository([usuario])
    clock = FixedClock(datetime(2026, 1, 1, 12, tzinfo=UTC))
    service = AutenticarUsuario(
        repository=repository,
        hasher=hasher,
        token_service=PyJwtTokenService(clock),
        clock=clock,
        dummy_password_hash=hasher.hash("dummy-password"),
    )
    return service, repository


def test_authentication_success(
    authentication_case: tuple[AutenticarUsuario, InMemoryUsuarioRepository],
) -> None:
    service, _ = authentication_case
    usuario, token = service.login("operador", "correcta")
    assert usuario.username == "operador"
    assert token


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("operador", "incorrecta"),
        ("inexistente", "correcta"),
    ],
)
def test_authentication_failures_share_error(
    authentication_case: tuple[AutenticarUsuario, InMemoryUsuarioRepository],
    username: str,
    password: str,
) -> None:
    service, repository = authentication_case
    inactive = Usuario(
        id=uuid4(),
        username="inactivo",
        password_hash=Argon2PasswordHasher().hash("correcta"),
        rol=Rol.OPERADOR,
        activo=False,
    )
    repository.add(inactive)
    if username == "inexistente":
        password = "correcta"

    with pytest.raises(CredencialesInvalidasError):
        service.login(username, password)


def test_inactive_user_has_same_error(
    authentication_case: tuple[AutenticarUsuario, InMemoryUsuarioRepository],
) -> None:
    service, repository = authentication_case
    repository.add(
        Usuario(
            id=uuid4(),
            username="inactivo",
            password_hash=Argon2PasswordHasher().hash("correcta"),
            rol=Rol.OPERADOR,
            activo=False,
        )
    )

    with pytest.raises(CredencialesInvalidasError):
        service.login("inactivo", "correcta")
