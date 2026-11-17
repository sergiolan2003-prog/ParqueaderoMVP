from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.tarifas.application.schemas import TarifaCreate, TarifaResponse
from app.modules.tarifas.domain.services import crear_o_actualizar_tarifa

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])

@router.post("/", response_model=TarifaResponse, status_code=status.HTTP_201_CREATED)
def administrar_tarifa(tarifa_data: TarifaCreate, db: Session = Depends(get_db)):
    return crear_o_actualizar_tarifa(db=db, tarifa_data=tarifa_data)