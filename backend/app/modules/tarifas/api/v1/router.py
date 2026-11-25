from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.tarifas.application.schemas import TarifaCreate, TarifaResponse
from app.modules.tarifas.application.services import (
    crear_o_actualizar_tarifa,
    listar_tarifas,
)

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])


@router.get(
    "/",
    response_model=list[TarifaResponse],
    dependencies=[Depends(requiere_rol(Rol.ADMINISTRADOR))],
)
def consultar_tarifas(
    sede_id: UUID | None = None,
    tipo_vehiculo: Literal["CARRO", "MOTO"] | None = Query(default=None),
    franja: Literal["DIURNA", "NOCTURNA"] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TarifaResponse]:
    return [
        TarifaResponse.model_validate(tarifa)
        for tarifa in listar_tarifas(
            db,
            sede_id=sede_id,
            tipo_vehiculo=tipo_vehiculo,
            franja=franja,
        )
    ]


@router.post(
    "/",
    response_model=TarifaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_rol(Rol.ADMINISTRADOR))],
)
def administrar_tarifa(
    tarifa_data: TarifaCreate,
    db: Session = Depends(get_db),
) -> TarifaResponse:
    return crear_o_actualizar_tarifa(db=db, tarifa_data=tarifa_data)
