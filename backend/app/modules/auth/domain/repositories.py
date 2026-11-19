from typing import Protocol

from app.modules.auth.domain.entities import Usuario


class UsuarioRepository(Protocol):
    def obtener_por_username(self, username: str) -> Usuario | None: ...

    def add(self, usuario: Usuario) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class TokenService(Protocol):
    def emitir(self, username: str, rol: str) -> str: ...

    def validar(self, token: str) -> tuple[str, str]: ...
