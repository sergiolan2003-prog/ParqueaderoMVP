# backend/tests/unit/test_motor_cobro.py
import pytest
from datetime import datetime
from app.modules.cobros.domain.motor_cobro import (
    EstrategiaCobroMoto,
    EstrategiaCobroCarro,
    MotorCobro
)

# Mocks para inyectar
class MockReloj:
    def __init__(self, franja_simulada: str):
        self.franja_simulada = franja_simulada
    def determinar_franja(self, fecha_hora: datetime) -> str:
        return self.franja_simulada

class MockTarifaRepo:
    def obtener_tarifa_activa(self, tipo_vehiculo: str, franja: str) -> float:
        if tipo_vehiculo == "CARRO" and franja == "DIURNA":
            return 5000.0
        elif tipo_vehiculo == "CARRO" and franja == "NOCTURNA":
            return 8000.0
        return None

def test_moto_siempre_es_cero():
    estrategia = EstrategiaCobroMoto()
    motor = MotorCobro(estrategia)
    fecha_ingreso = datetime(2026, 11, 18, 8, 0)
    
    assert motor.liquidar(fecha_ingreso) == 0.0

def test_carro_tarifa_diurna():
    repo = MockTarifaRepo()
    reloj = MockReloj("DIURNA")
    estrategia = EstrategiaCobroCarro(repo, reloj)
    motor = MotorCobro(estrategia)
    
    # 08:00 AM
    fecha_ingreso = datetime(2026, 11, 18, 8, 0)
    assert motor.liquidar(fecha_ingreso) == 5000.0

def test_carro_tarifa_nocturna():
    repo = MockTarifaRepo()
    reloj = MockReloj("NOCTURNA")
    estrategia = EstrategiaCobroCarro(repo, reloj)
    motor = MotorCobro(estrategia)
    
    # 19:00 PM
    fecha_ingreso = datetime(2026, 11, 18, 19, 0)
    assert motor.liquidar(fecha_ingreso) == 8000.0

def test_carro_sin_tarifa_lanza_error():
    repo = MockTarifaRepo()
    reloj = MockReloj("FESTIVA") # Franja no configurada en el mock
    estrategia = EstrategiaCobroCarro(repo, reloj)
    motor = MotorCobro(estrategia)
    
    with pytest.raises(ValueError) as exc:
        motor.liquidar(datetime.now())
    assert "No hay tarifa configurada" in str(exc.value)