from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accesos.infrastructure.models import Sede


def listar_sedes(db: Session) -> list[Sede]:
    return db.query(Sede).order_by(Sede.nombre, Sede.id).all()


def obtener_sede(db: Session, sede_id: UUID) -> Sede | None:
    return db.query(Sede).filter(Sede.id == sede_id).first()


def actualizar_cupos(
    db: Session,
    *,
    sede_id: UUID,
    cupos_carro: int,
    cupos_moto: int,
) -> Sede | None:
    sede = obtener_sede(db, sede_id)
    if sede is None:
        return None

    sede.cupos_carro = cupos_carro
    sede.cupos_moto = cupos_moto
    db.commit()
    db.refresh(sede)
    return sede
