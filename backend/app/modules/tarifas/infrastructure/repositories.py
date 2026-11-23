from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.cobros.domain.motor_cobro import TarifaAplicable
from app.modules.tarifas.infrastructure.models import Tarifa


class SqlAlchemyTarifaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obtener_tarifa_activa(
        self,
        sede_id: UUID,
        tipo_vehiculo: str,
        franja: str,
        dia_operativo: date,
    ) -> TarifaAplicable | None:
        tarifa = (
            self._session.query(Tarifa)
            .filter(
                Tarifa.sede_id == sede_id,
                Tarifa.tipo_vehiculo == tipo_vehiculo,
                Tarifa.franja == franja,
                Tarifa.vigente_desde <= dia_operativo,
                (Tarifa.vigente_hasta.is_(None))
                | (Tarifa.vigente_hasta >= dia_operativo),
            )
            .order_by(Tarifa.vigente_desde.desc())
            .first()
        )
        if tarifa is None:
            return None
        return TarifaAplicable(id=tarifa.id, valor=tarifa.valor)
