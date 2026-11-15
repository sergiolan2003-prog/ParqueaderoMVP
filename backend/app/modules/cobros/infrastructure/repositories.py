from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.cobros.domain.entities import Cobro
from app.modules.cobros.domain.exceptions import CobroDuplicadoError
from app.modules.cobros.infrastructure import constraints
from app.modules.cobros.infrastructure.models import Cobro as CobroModel


class SqlAlchemyCobroRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, cobro: Cobro) -> None:
        """Flush without commit; the caller must rollback or use a
        savepoint on error.
        """
        self._session.add(
            CobroModel(
                id=cobro.id,
                placa=cobro.placa,
                sede_id=cobro.sede_id,
                dia_operativo=cobro.dia_operativo,
                tarifa_id=cobro.tarifa_id,
                valor=cobro.valor,
                estado=cobro.estado,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            diag = getattr(exc.orig, "diag", None)
            if (
                getattr(diag, "constraint_name", None)
                == constraints.COBRO_PLACA_SEDE_DIA_UNIQUE
            ):
                raise CobroDuplicadoError(
                    "Ya existe un cobro para la placa, sede y día operativo."
                ) from exc
            raise
