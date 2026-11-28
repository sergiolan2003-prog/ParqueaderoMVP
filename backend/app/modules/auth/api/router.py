from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.database import get_db
from app.modules.auth.api.dependencies import get_usuario_actual, requiere_rol
from app.modules.auth.api.schemas import TokenResponse, UsuarioResponse
from app.modules.auth.application.services import AutenticarUsuario
from app.modules.auth.domain.entities import IdentidadAutenticada, Rol
from app.modules.auth.domain.exceptions import CredencialesInvalidasError
from app.modules.auth.infrastructure.passwords import Argon2PasswordHasher
from app.modules.auth.infrastructure.repositories import SqlAlchemyUsuarioRepository
from app.modules.auth.infrastructure.tokens import PyJwtTokenService

router = APIRouter(prefix="/auth", tags=["Autenticación"])

PASSWORD_HASHER = Argon2PasswordHasher()
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("dummy-password")


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    clock = SystemClock()
    case = AutenticarUsuario(
        repository=SqlAlchemyUsuarioRepository(db),
        hasher=PASSWORD_HASHER,
        token_service=PyJwtTokenService(clock),
        clock=clock,
        dummy_password_hash=DUMMY_PASSWORD_HASH,
    )
    try:
        _, token = case.login(form.username, form.password)
    except CredencialesInvalidasError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UsuarioResponse)
def me(
    usuario: IdentidadAutenticada = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
) -> UsuarioResponse:
    usuario_db = SqlAlchemyUsuarioRepository(db).obtener_por_username(usuario.username)
    if usuario_db is None:
        raise HTTPException(status_code=401, detail="Usuario no válido.")
    return UsuarioResponse(
        username=usuario_db.username,
        rol=usuario_db.rol.value,
        activo=usuario_db.activo,
    )


@router.get("/admin-check")
def admin_check(
    usuario: IdentidadAutenticada = Depends(requiere_rol(Rol.ADMINISTRADOR)),
) -> dict[str, str]:
    return {
        "mensaje": "Acceso de administrador permitido.",
        "username": usuario.username,
    }
