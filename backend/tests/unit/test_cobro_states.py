import pytest

from app.modules.cobros.domain.states import (
    CobroAnulado,
    CobroPagado,
    CobroPendiente,
    TransicionCobroInvalidaError,
)


def test_pending_charge_can_transition_to_paid_and_not_authorize_exit() -> None:
    pending = CobroPendiente()

    paid = pending.confirmar_pago()

    assert isinstance(paid, CobroPagado)
    assert pending.autoriza_salida(pase_vigente=True) is False


def test_paid_charge_requires_a_current_pass_for_exit() -> None:
    paid = CobroPagado()

    assert paid.autoriza_salida(pase_vigente=True) is True
    assert paid.autoriza_salida(pase_vigente=False) is False
    with pytest.raises(TransicionCobroInvalidaError):
        paid.confirmar_pago()


def test_cancelled_charge_cannot_be_paid_or_authorize_exit() -> None:
    cancelled = CobroAnulado()

    assert cancelled.autoriza_salida(pase_vigente=True) is False
    with pytest.raises(TransicionCobroInvalidaError):
        cancelled.confirmar_pago()
