from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.modules.tarifas.application.schemas import TarifaCreate
from app.modules.tarifas.infrastructure.models import Tarifa


def crear_o_actualizar_tarifa(
    db: Session,
    tarifa_data: TarifaCreate,
) -> Tarifa:
    franja_opuesta = "NOCTURNA" if tarifa_data.franja.upper() == "DIURNA" else "DIURNA"
    tarifa_existente_opuesta = (
        db.query(Tarifa)
        .filter(
            Tarifa.sede_id == tarifa_data.sede_id,
            Tarifa.tipo_vehiculo == tarifa_data.tipo_vehiculo.upper(),
            Tarifa.franja == franja_opuesta,
            Tarifa.vigente_desde <= tarifa_data.vigente_desde,
            or_(
                Tarifa.vigente_hasta.is_(None),
                Tarifa.vigente_hasta >= tarifa_data.vigente_desde,
            ),
        )
        .first()
    )

    if tarifa_existente_opuesta:
        if tarifa_data.franja.upper() == "DIURNA":
            if tarifa_data.valor <= tarifa_existente_opuesta.valor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "RN-02: La tarifa diurna debe ser mayor estricta "
                        "que la tarifa nocturna."
                    ),
                )
        elif tarifa_data.valor >= tarifa_existente_opuesta.valor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "RN-02: La tarifa nocturna no puede ser mayor o igual "
                    "a la tarifa diurna."
                ),
            )

    tarifa_actual = (
        db.query(Tarifa)
        .filter(
            Tarifa.sede_id == tarifa_data.sede_id,
            Tarifa.tipo_vehiculo == tarifa_data.tipo_vehiculo.upper(),
            Tarifa.franja == tarifa_data.franja.upper(),
            Tarifa.vigente_hasta.is_(None),
        )
        .first()
    )

    if tarifa_actual:
        if tarifa_data.vigente_desde <= tarifa_actual.vigente_desde:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La nueva tarifa debe iniciar después de la vigencia "
                    "de la tarifa actual."
                ),
            )
        tarifa_actual.vigente_hasta = tarifa_data.vigente_desde - timedelta(days=1)

    nueva_tarifa = Tarifa(
        sede_id=tarifa_data.sede_id,
        tipo_vehiculo=tarifa_data.tipo_vehiculo.upper(),
        franja=tarifa_data.franja.upper(),
        valor=tarifa_data.valor,
        vigente_desde=tarifa_data.vigente_desde,
        vigente_hasta=tarifa_data.vigente_hasta,
    )
    db.add(nueva_tarifa)
    db.commit()
    db.refresh(nueva_tarifa)
    return nueva_tarifa
