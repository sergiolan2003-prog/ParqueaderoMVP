import re
from random import Random

from app.modules.accesos.domain.lectores import (
    LecturaPlaca,
    LectorManual,
    LectorPlaca,
    LectorSimulado,
)


def _leer(lector: LectorPlaca) -> LecturaPlaca:
    return lector.leer()


def test_simulated_reader_uses_injected_random_source() -> None:
    first = _leer(LectorSimulado(Random(42)))
    second = _leer(LectorSimulado(Random(42)))

    assert first == second
    assert 0 <= first.confianza <= 1
    assert re.fullmatch(r"[A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z]", first.placa)


def test_simulated_reader_accepts_explicit_plate_and_confidence() -> None:
    result = _leer(LectorSimulado(Random(1), placa="ABC123", confianza=0.95))

    assert result == LecturaPlaca(placa="ABC123", confianza=0.95)


def test_manual_reader_returns_full_confidence_and_manual_flag() -> None:
    result = _leer(LectorManual("abc123"))

    assert result == LecturaPlaca(
        placa="abc123",
        confianza=1.0,
        lectura_manual=True,
    )
