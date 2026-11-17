from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.modules.tarifas.infrastructure.models import Tarifa
from app.modules.tarifas.application.schemas import TarifaCreate

def crear_o_actualizar_tarifa(db: Session, tarifa_data: TarifaCreate) -> Tarifa:
    # Regla de negocio RN-02: Validar la relación entre franjas si ya existe o se evalúa en conjunto
    # Si estamos creando una tarifa, verificamos si existe la contraparte para validar que nocturna < diurna
    franja_opuesta = "NOCTURNA" if tarifa_data.franja.upper() == "DIURNA" else "DIURNA"
    
    tarifa_existente_opuesta = db.query(Tarifa).filter(
        Tarifa.sede_id == tarifa_data.sede_id,
        Tarifa.tipo_vehiculo == tarifa_data.tipo_vehiculo.upper(),
        Tarifa.franja == franja_opuesta,
        Tarifa.vigente_hasta.is_(None) # Vigente actual
    ).first()

    if tarifa_existente_opuesta:
        if tarifa_data.franja.upper() == "DIURNA":
            # tarifa_data es DIURNA, la opuesta es NOCTURNA -> DIURNA debe ser mayor que NOCTURNA
            if tarifa_data.valor <= tarifa_existente_opuesta.valor:
                raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RN-02: La tarifa diurna debe ser mayor estricta que la tarifa nocturna."
            )
        else:
            # tarifa_data es NOCTURNA, la opuesta es DIURNA -> NOCTURNA debe ser menor que DIURNA
            if tarifa_data.valor >= tarifa_existente_opuesta.valor:
                raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RN-02: La tarifa nocturna no puede ser mayor o igual a la tarifa diurna."
            )

    # Cierre de la versión anterior vigente para este tipo de vehículo y franja
    tarifa_actual = db.query(Tarifa).filter(
        Tarifa.sede_id == tarifa_data.sede_id,
        Tarifa.tipo_vehiculo == tarifa_data.tipo_vehiculo.upper(),
        Tarifa.franja == tarifa_data.franja.upper(),
        Tarifa.vigente_hasta.is_(None)
    ).first()

    if tarifa_actual:
        # Cerramos la vigencia de la anterior para cumplir con el versionamiento
        tarifa_actual.vigente_hasta = tarifa_data.vigente_desde

    # Creamos la nueva versión de la tarifa
    nueva_tarifa = Tarifa(
        sede_id=tarifa_data.sede_id,
        tipo_vehiculo=tarifa_data.tipo_vehiculo.upper(),
        franja=tarifa_data.franja.upper(),
        valor=tarifa_data.valor,
        vigente_desde=tarifa_data.vigente_desde,
        vigente_hasta=tarifa_data.vigente_hasta
    )

    db.add(nueva_tarifa)
    db.commit()
    db.refresh(nueva_tarifa)
    return nueva_tarifa