from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cobros.infrastructure.models import Cobro
from app.modules.pases.domain.entities import Pase
from app.modules.pases.infrastructure.models import Pase as PaseModel


class SqlAlchemyPaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, pase: Pase) -> None:
        self._session.add(
            PaseModel(
                id=pase.id,
                cobro_id=pase.cobro_id,
                dia_operativo=pase.dia_operativo,
                placa=pase.placa,
                sede_id=pase.sede_id,
                vigente_desde=pase.vigente_desde,
                vigente_hasta=pase.vigente_hasta,
            )
        )
        self._session.flush()

    def get_by_charge_id(self, charge_id: UUID) -> Pase | None:
        row = self._session.execute(
            select(PaseModel, Cobro.dia_operativo)
            .join(Cobro, Cobro.id == PaseModel.cobro_id)
            .where(PaseModel.cobro_id == charge_id)
        ).one_or_none()
        if row is None:
            return None
        model, operating_day = row
        return Pase(
            id=model.id,
            cobro_id=model.cobro_id,
            placa=model.placa,
            sede_id=model.sede_id,
            dia_operativo=model.dia_operativo or operating_day,
            vigente_desde=model.vigente_desde,
            vigente_hasta=model.vigente_hasta,
        )
