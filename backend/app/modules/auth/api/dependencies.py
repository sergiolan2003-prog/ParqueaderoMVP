from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.database import get_db
from app.modules.auth.domain.entities import IdentidadAutenticada, Rol
from app.modules.auth.domain.exceptions import (
    TokenExpiradoError,
    TokenInvalidoError,
)
from app.modules.auth.infrastructure.repositories import SqlAlchemyUsuarioRepository
from app.modules.auth.infrastructure.tokens import PyJwtTokenService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_usuario_actual(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> IdentidadAutenticada:
    if token is None:
        raise _unauthorized("Se requiere un token Bearer.")
    try:
        username, rol = PyJwtTokenService(SystemClock()).validar(token)
    except (TokenExpiradoError, TokenInvalidoError):
        raise _unauthorized("Token inválido o expirado.") from None

    usuario = SqlAlchemyUsuarioRepository(db).obtener_por_username(username)
    if usuario is None or not usuario.activo:
        raise _unauthorized("Token inválido o expirado.")
    return IdentidadAutenticada(username=username, rol=Rol(rol))


def requiere_rol(rol_requerido: Rol) -> Callable:
    def dependencia(
        usuario: IdentidadAutenticada = Depends(get_usuario_actual),
    ) -> IdentidadAutenticada:
        if usuario.rol != rol_requerido:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para esta operación.",
            )
        return usuario

    return dependencia


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
