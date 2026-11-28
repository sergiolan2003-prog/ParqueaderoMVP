import re
from random import Random

from app.modules.accesos.domain.lectores import (
    LectorImagenSimulado,
    LectorManual,
    LectorPlaca,
    LectorSimulado,
    LecturaPlaca,
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


def test_image_reader_uses_filename_plate_and_confidence() -> None:
    result = LectorImagenSimulado("ABC123_0.92.jpg").leer()

    assert result == LecturaPlaca(placa="ABC123", confianza=0.92)


def test_image_reader_overrides_filename_values() -> None:
    result = LectorImagenSimulado(
        "ABC123_0.92.jpg",
        placa_simulada="XYZ789",
        confianza_simulada=0.40,
    ).leer()

    assert result == LecturaPlaca(placa="XYZ789", confianza=0.40)


def test_image_reader_normalizes_plate_with_spaces_or_hyphens() -> None:
    result = LectorImagenSimulado("abc-123_0.95.jpg").leer()

    assert result == LecturaPlaca(placa="ABC123", confianza=0.95)
