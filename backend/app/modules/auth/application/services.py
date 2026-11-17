from app.core.clock import Clock
from app.modules.auth.domain.entities import Usuario
from app.modules.auth.domain.exceptions import CredencialesInvalidasError
from app.modules.auth.domain.repositories import (
    PasswordHasher,
    TokenService,
    UsuarioRepository,
)


class AutenticarUsuario:
    def __init__(
        self,
        repository: UsuarioRepository,
        hasher: PasswordHasher,
        token_service: TokenService,
        clock: Clock,
        dummy_password_hash: str,
    ) -> None:
        self._repository = repository
        self._hasher = hasher
        self._token_service = token_service
        self._clock = clock
        self._dummy_password_hash = dummy_password_hash

    def login(self, username: str, password: str) -> tuple[Usuario, str]:
        usuario = self._repository.obtener_por_username(username)
        if usuario is None:
            self._hasher.verify(self._dummy_password_hash, password)
            raise CredencialesInvalidasError("Credenciales inválidas.")

        if not usuario.activo:
            self._hasher.verify(usuario.password_hash, password)
            raise CredencialesInvalidasError("Credenciales inválidas.")

        if not self._hasher.verify(usuario.password_hash, password):
            raise CredencialesInvalidasError("Credenciales inválidas.")

        self._clock.now()
        token = self._token_service.emitir(usuario.username, usuario.rol.value)
        return usuario, token
