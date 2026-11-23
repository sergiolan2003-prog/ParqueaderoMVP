# backend/tests/unit/test_clasificador_placa.py
import pytest
from app.modules.accesos.domain.placa import ClasificadorPlaca, PlacaInvalidaError

def test_clasificar_carro():
    assert ClasificadorPlaca.clasificar("ABC123") == "CARRO"

def test_clasificar_moto():
    assert ClasificadorPlaca.clasificar("ABC12D") == "MOTO"

def test_normalizar_y_clasificar_carro():
    assert ClasificadorPlaca.clasificar("abc 123") == "CARRO"
    assert ClasificadorPlaca.clasificar("abc-123") == "CARRO"

@pytest.mark.parametrize("placa_invalida", [
    "AB1234",   # Faltan letras
    "ABCD12",   # Sobran letras
    "",         # Vacía
    "   ",      # Solo espacios
])
def test_clasificar_placa_invalida_lanza_error(placa_invalida):
    with pytest.raises(PlacaInvalidaError) as exc_info:
        ClasificadorPlaca.clasificar(placa_invalida)
    assert "invalido" in str(exc_info.value).lower() or "vacía" in str(exc_info.value).lower()