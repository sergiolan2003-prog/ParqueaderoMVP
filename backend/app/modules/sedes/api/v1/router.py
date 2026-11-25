from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.sedes.application.schemas import CuposUpdate, SedeResponse
from app.modules.sedes.application.services import (
    actualizar_cupos,
    listar_sedes,
    obtener_sede,
)

router = APIRouter(prefix="/sedes", tags=["Sedes"])
admin_dependency = Depends(requiere_rol(Rol.ADMINISTRADOR))


@router.get(
    "/",
    response_model=list[SedeResponse],
    dependencies=[admin_dependency],
)
def consultar_sedes(db: Session = Depends(get_db)) -> list[SedeResponse]:
    return [
        SedeResponse.model_validate(sede)
        for sede in listar_sedes(db)
    ]


@router.get(
    "/{sede_id}/cupos",
    response_model=SedeResponse,
    dependencies=[admin_dependency],
)
def consultar_cupos(sede_id: UUID, db: Session = Depends(get_db)) -> SedeResponse:
    sede = obtener_sede(db, sede_id)
    if sede is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sede especificada no existe.",
        )
    return SedeResponse.model_validate(sede)


@router.put(
    "/{sede_id}/cupos",
    response_model=SedeResponse,
    dependencies=[admin_dependency],
)
def modificar_cupos(
    sede_id: UUID,
    cupos: CuposUpdate,
    db: Session = Depends(get_db),
) -> SedeResponse:
    sede = actualizar_cupos(
        db,
        sede_id=sede_id,
        cupos_carro=cupos.cupos_carro,
        cupos_moto=cupos.cupos_moto,
    )
    if sede is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sede especificada no existe.",
        )
    return SedeResponse.model_validate(sede)
