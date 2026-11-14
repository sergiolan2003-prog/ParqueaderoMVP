from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.pagos.domain.entities import Pago
from app.modules.pagos.domain.exceptions import PagoDuplicadoError
from app.modules.pagos.infrastructure import constraints
from app.modules.pagos.infrastructure.models import Pago as PagoModel


class SqlAlchemyPagoRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, pago: Pago) -> None:
        """Flush without commit; the caller must rollback or use a savepoint on error."""
        self._session.add(
            PagoModel(
                id=pago.id,
                cobro_id=pago.cobro_id,
                medio=pago.medio,
                valor=pago.valor,
                referencia_pasarela=pago.referencia_pasarela,
                pagado_en=pago.pagado_en,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            diag = getattr(exc.orig, "diag", None)
            if (
                getattr(diag, "constraint_name", None)
                == constraints.PAGO_REFERENCIA_UNIQUE
            ):
                raise PagoDuplicadoError(
                    "La referencia de pago ya fue registrada."
                ) from exc
            raise
