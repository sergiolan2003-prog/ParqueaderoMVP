from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.configuracion.application.schemas import (
    ConfiguracionOperativaResponse,
    ConfiguracionOperativaUpdate,
)
from app.modules.configuracion.application.services import (
    actualizar_configuracion_operativa,
    obtener_configuracion_operativa,
)

router = APIRouter(prefix="/configuracion", tags=["Configuración"])
admin_dependency = Depends(requiere_rol(Rol.ADMINISTRADOR))


@router.get(
    "/operativa",
    response_model=ConfiguracionOperativaResponse,
    dependencies=[admin_dependency],
)
def consultar_configuracion_operativa(
    db: Session = Depends(get_db),
) -> ConfiguracionOperativaResponse:
    return obtener_configuracion_operativa(db)


@router.put(
    "/operativa",
    response_model=ConfiguracionOperativaResponse,
    dependencies=[admin_dependency],
)
def modificar_configuracion_operativa(
    configuracion: ConfiguracionOperativaUpdate,
    db: Session = Depends(get_db),
) -> ConfiguracionOperativaResponse:
    return actualizar_configuracion_operativa(db, configuracion)
