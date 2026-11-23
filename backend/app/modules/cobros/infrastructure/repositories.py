from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.cobros.domain.entities import Cobro
from app.modules.cobros.infrastructure import constraints
from app.modules.cobros.infrastructure.models import Cobro as CobroModel


class SqlAlchemyCobroRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, cobro: Cobro) -> bool:
        """Insert a charge unless this plate already has one for that day."""
        result = self._session.execute(
            insert(CobroModel)
            .values(
                id=cobro.id,
                placa=cobro.placa,
                sede_id=cobro.sede_id,
                dia_operativo=cobro.dia_operativo,
                tarifa_id=cobro.tarifa_id,
                valor=cobro.valor,
                estado=cobro.estado,
            )
            .on_conflict_do_nothing(
                constraint=constraints.COBRO_PLACA_SEDE_DIA_UNIQUE,
            )
            .returning(CobroModel.id)
        )
        return result.scalar_one_or_none() is not None
