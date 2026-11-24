from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.cobros.domain.motor_cobro import (
    EstrategiaCobroConfigurada,
    MotorCobro,
    TarifaAplicable,
    TarifaNoConfiguradaError,
)


class MockOperatingDay:
    def __init__(self, franja: str, dia: date = date(2026, 11, 18)) -> None:
        self._franja = franja
        self._dia = dia

    def dia_operativo(self, instante: datetime | None = None) -> date:
        return self._dia

    def franja(self, instante: datetime | None = None) -> str:
        return self._franja


class MockTarifaRepository:
    def __init__(self, tarifas: dict[tuple[str, str], Decimal]) -> None:
        self._tarifas = tarifas
        self.ultima_consulta: tuple[UUID, str, str, date] | None = None

    def obtener_tarifa_activa(
        self,
        sede_id: UUID,
        tipo_vehiculo: str,
        franja: str,
        dia_operativo: date,
    ) -> TarifaAplicable | None:
        self.ultima_consulta = (sede_id, tipo_vehiculo, franja, dia_operativo)
        valor = self._tarifas.get((tipo_vehiculo, franja))
        if valor is None:
            return None
        return TarifaAplicable(id=uuid4(), valor=valor)


def _motor(
    tarifas: dict[tuple[str, str], Decimal],
    franja: str,
) -> tuple[MotorCobro, MockTarifaRepository]:
    repo = MockTarifaRepository(tarifas)
    motor = MotorCobro(
        EstrategiaCobroConfigurada(repo, MockOperatingDay(franja))
    )
    return motor, repo


@pytest.mark.parametrize(
    ("tipo", "franja", "importe"),
    [
        ("CARRO", "DIURNA", Decimal("5000.00")),
        ("CARRO", "NOCTURNA", Decimal("8000.00")),
        ("MOTO", "DIURNA", Decimal("0.00")),
    ],
)
def test_motor_resuelve_el_valor_configurado_incluida_tarifa_cero(
    tipo: str,
    franja: str,
    importe: Decimal,
) -> None:
    motor, repo = _motor({(tipo, franja): importe}, franja)
    sede_id = uuid4()

    liquidacion = motor.liquidar(
        sede_id,
        tipo,
        datetime(2026, 11, 18, 8, 0, tzinfo=UTC),
    )

    assert liquidacion.tarifa.valor == importe
    assert liquidacion.dia_operativo == date(2026, 11, 18)
    assert repo.ultima_consulta == (
        sede_id,
        tipo,
        franja,
        date(2026, 11, 18),
    )


def test_motor_falla_claramente_si_no_hay_tarifa_activa() -> None:
    motor, _ = _motor({}, "NOCTURNA")

    with pytest.raises(TarifaNoConfiguradaError, match="CARRO.*NOCTURNA"):
        motor.liquidar(
            uuid4(),
            "CARRO",
            datetime(2026, 11, 18, 19, 0, tzinfo=UTC),
        )
