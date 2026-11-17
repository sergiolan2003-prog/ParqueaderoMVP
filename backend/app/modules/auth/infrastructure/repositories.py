from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.domain.entities import Rol, Usuario
from app.modules.auth.domain.exceptions import UsuarioDuplicadoError
from app.modules.auth.infrastructure import constraints
from app.modules.auth.infrastructure.models import Usuario as UsuarioModel


class SqlAlchemyUsuarioRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obtener_por_username(self, username: str) -> Usuario | None:
        model = (
            self._session.query(UsuarioModel)
            .filter(UsuarioModel.username == username)
            .first()
        )
        if model is None:
            return None
        return Usuario(
            id=model.id,
            username=model.username,
            password_hash=model.password_hash,
            rol=Rol(model.rol),
            activo=model.activo,
        )

    def add(self, usuario: Usuario) -> None:
        self._session.add(
            UsuarioModel(
                id=usuario.id,
                username=usuario.username,
                password_hash=usuario.password_hash,
                rol=usuario.rol.value,
                activo=usuario.activo,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            diag = getattr(exc.orig, "diag", None)
            if (
                getattr(diag, "constraint_name", None)
                == constraints.USUARIO_USERNAME_UNIQUE
            ):
                raise UsuarioDuplicadoError(
                    "Ya existe un usuario con ese nombre."
                ) from exc
            raise
