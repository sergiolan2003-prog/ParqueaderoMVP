from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.pagos.domain.entities import Pago
from app.modules.pagos.domain.exceptions import (
    PagoCobroDuplicadoError,
    PagoDuplicadoError,
)
from app.modules.pagos.infrastructure import constraints
from app.modules.pagos.infrastructure.models import Pago as PagoModel


class SqlAlchemyPagoRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, pago: Pago) -> None:
        """Flush without commit; the caller must rollback or use a
        savepoint on error.
        """
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
            constraint_name = getattr(diag, "constraint_name", None)
            if constraint_name == constraints.PAGO_REFERENCIA_UNIQUE:
                raise PagoDuplicadoError(
                    "La referencia de pago ya fue registrada."
                ) from exc
            if constraint_name == constraints.PAGO_COBRO_UNIQUE:
                raise PagoCobroDuplicadoError(
                    "El cobro ya tiene un pago registrado."
                ) from exc
            raise

    def get_by_reference(self, reference: str) -> Pago | None:
        model = self._session.scalar(
            select(PagoModel).where(PagoModel.referencia_pasarela == reference)
        )
        return self._to_entity(model) if model is not None else None

    def get_by_charge_id(self, charge_id: UUID) -> Pago | None:
        model = self._session.scalar(
            select(PagoModel).where(PagoModel.cobro_id == charge_id)
        )
        return self._to_entity(model) if model is not None else None

    @staticmethod
    def _to_entity(model: PagoModel) -> Pago:
        return Pago(
            id=model.id,
            cobro_id=model.cobro_id,
            medio=model.medio,
            valor=model.valor,
            referencia_pasarela=model.referencia_pasarela,
            pagado_en=model.pagado_en,
        )
