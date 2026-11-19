from datetime import UTC, timedelta

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.clock import Clock
from app.core.config import settings
from app.modules.auth.domain.exceptions import (
    TokenExpiradoError,
    TokenInvalidoError,
)


class PyJwtTokenService:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def emitir(self, username: str, rol: str) -> str:
        now = self._clock.now().astimezone(UTC)
        expires = now + timedelta(minutes=settings.jwt_expire_minutes)
        return jwt.encode(
            {
                "sub": username,
                "rol": rol,
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

    def validar(self, token: str) -> tuple[str, str]:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                options={
                    "require": ["sub", "rol", "iat", "exp"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            expiration = payload.get("exp")
            if not isinstance(expiration, int):
                raise TokenInvalidoError("El token no contiene expiración válida.")
            now = int(self._clock.now().timestamp())
            if expiration <= now:
                raise TokenExpiradoError("El token ha expirado.")
            username = payload.get("sub")
            rol = payload.get("rol")
            if not isinstance(username, str) or rol not in {
                "OPERADOR",
                "ADMINISTRADOR",
            }:
                raise TokenInvalidoError("El token no contiene identidad válida.")
            return username, rol
        except ExpiredSignatureError as exc:
            raise TokenExpiradoError("El token ha expirado.") from exc
        except InvalidTokenError as exc:
            raise TokenInvalidoError("El token es inválido.") from exc
