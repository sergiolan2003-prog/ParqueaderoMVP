from sqlalchemy.orm import Session

from app.modules.accesos.infrastructure.models import Carril, Sede


def listar_carriles(db: Session) -> list[tuple[Carril, str]]:
    return (
        db.query(Carril, Sede.nombre)
        .join(Sede, Carril.sede_id == Sede.id)
        .order_by(Sede.nombre, Carril.sentido, Carril.id)
        .all()
    )
