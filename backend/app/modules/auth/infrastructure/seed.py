from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.auth.domain.entities import Rol, Usuario
from app.modules.auth.infrastructure.passwords import Argon2PasswordHasher
from app.modules.auth.infrastructure.repositories import SqlAlchemyUsuarioRepository


def seed_users(session: Session) -> None:
    hasher = Argon2PasswordHasher()
    repository = SqlAlchemyUsuarioRepository(session)
    users = (
        (
            settings.seed_admin_username,
            settings.seed_admin_password,
            Rol.ADMINISTRADOR,
        ),
        (
            settings.seed_operador_username,
            settings.seed_operador_password,
            Rol.OPERADOR,
        ),
    )
    for username, password, rol in users:
        if repository.obtener_por_username(username) is not None:
            continue
        repository.add(
            Usuario(
                id=uuid4(),
                username=username,
                password_hash=hasher.hash(password),
                rol=rol,
                activo=True,
            )
        )
    session.commit()


def main() -> None:
    session = SessionLocal()
    try:
        seed_users(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
