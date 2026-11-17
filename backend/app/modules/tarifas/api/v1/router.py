from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.tarifas.application.schemas import TarifaCreate, TarifaResponse
from app.modules.tarifas.application.services import crear_o_actualizar_tarifa

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])


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
