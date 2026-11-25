from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.configuracion.application.schemas import (
    ConfiguracionOperativaResponse,
    ConfiguracionOperativaUpdate,
)
from app.modules.configuracion.infrastructure.models import ConfiguracionOperativa


def obtener_configuracion_operativa(
    db: Session,
) -> ConfiguracionOperativaResponse:
    configuracion = db.get(ConfiguracionOperativa, 1)
    if configuracion is not None:
        return ConfiguracionOperativaResponse.model_validate(configuracion)

    return ConfiguracionOperativaResponse(
        daytime_start=settings.daytime_start,
        daytime_end=settings.daytime_end,
        nighttime_start=settings.nighttime_start,
        nighttime_end=settings.nighttime_end,
        lpr_confidence_threshold=settings.lpr_confidence_threshold,
    )


def actualizar_configuracion_operativa(
    db: Session,
    configuracion: ConfiguracionOperativaUpdate,
) -> ConfiguracionOperativaResponse:
    values = configuracion.model_dump()
    statement = (
        insert(ConfiguracionOperativa)
        .values(id=1, **values)
        .on_conflict_do_update(
            index_elements=[ConfiguracionOperativa.id],
            set_=values,
        )
        .returning(ConfiguracionOperativa)
    )
    saved = db.execute(statement).scalar_one()
    db.commit()
    db.refresh(saved)
    return ConfiguracionOperativaResponse.model_validate(saved)
