from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.accesos.application.carriles import listar_carriles
from app.modules.auth.api.dependencies import get_usuario_actual

router = APIRouter(prefix="/carriles", tags=["Carriles"])


class CarrilDisponible(BaseModel):
    id: UUID
    sede_id: UUID
    sede_nombre: str
    sentido: Literal["ENTRADA", "SALIDA"]


@router.get(
    "/",
    response_model=list[CarrilDisponible],
    summary="Listar carriles disponibles",
    description=(
        "Devuelve los carriles de la sede para que el operador use el UUID "
        "internamente sin tener que ingresarlo manualmente."
    ),
    dependencies=[Depends(get_usuario_actual)],
)
def consultar_carriles(db: Session = Depends(get_db)) -> list[CarrilDisponible]:
    filas = listar_carriles(db)
    return [
        CarrilDisponible(
            id=carril.id,
            sede_id=carril.sede_id,
            sede_nombre=sede_nombre,
            sentido=carril.sentido,
        )
        for carril, sede_nombre in filas
    ]
