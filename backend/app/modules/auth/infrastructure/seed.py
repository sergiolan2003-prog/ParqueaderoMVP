from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.accesos.infrastructure.models import Carril, Sede
from app.modules.auth.domain.entities import Rol, Usuario
from app.modules.auth.infrastructure.passwords import Argon2PasswordHasher
from app.modules.auth.infrastructure.repositories import SqlAlchemyUsuarioRepository
from app.modules.tarifas.infrastructure.models import Tarifa


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


def seed_development_data(session: Session) -> None:
    site_name = "Sede Demo Parqueadero"
    site = session.scalar(select(Sede).where(Sede.nombre == site_name))
    if site is None:
        site = Sede(
            nombre=site_name,
            zona_horaria=settings.operating_timezone,
            inicio_dia_operativo=settings.operating_day_start,
            cupos_carro=100,
            cupos_moto=50,
        )
        session.add(site)
        session.flush()

    for direction in ("ENTRADA", "SALIDA"):
        lane = session.scalar(
            select(Carril).where(
                Carril.sede_id == site.id,
                Carril.sentido == direction,
            )
        )
        if lane is None:
            session.add(Carril(sede_id=site.id, sentido=direction))

    start_date = datetime.now(ZoneInfo(settings.operating_timezone)).date()
    tariffs = (
        ("CARRO", "DIURNA", Decimal("6000.00")),
        ("CARRO", "NOCTURNA", Decimal("4000.00")),
        ("MOTO", "DIURNA", Decimal("4000.00")),
        ("MOTO", "NOCTURNA", Decimal("2000.00")),
    )
    for vehicle_type, period, amount in tariffs:
        tariff_exists = session.scalar(
            select(Tarifa.id).where(
                Tarifa.sede_id == site.id,
                Tarifa.tipo_vehiculo == vehicle_type,
                Tarifa.franja == period,
            )
        )
        if tariff_exists is None:
            session.add(
                Tarifa(
                    sede_id=site.id,
                    tipo_vehiculo=vehicle_type,
                    franja=period,
                    valor=amount,
                    vigente_desde=start_date,
                )
            )

    session.commit()


def main() -> None:
    session = SessionLocal()
    try:
        seed_users(session)
        if settings.app_env == "development":
            seed_development_data(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
