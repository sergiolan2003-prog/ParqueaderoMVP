# backend/app/modules/cobros/domain/motor_cobro.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol

# Interfaces (Puertos) para inyección de dependencias
class TarifaRepository(Protocol):
    def obtener_tarifa_activa(self, tipo_vehiculo: str, franja: str) -> float:
        ...

class Reloj(Protocol):
    def determinar_franja(self, fecha_hora: datetime) -> str:
        ...

# Patrón Strategy
class EstrategiaCobro(ABC):
    @abstractmethod
    def calcular_tarifa(self, primer_ingreso: datetime) -> float:
        pass

class EstrategiaCobroMoto(EstrategiaCobro):
    def calcular_tarifa(self, primer_ingreso: datetime) -> float:
        # RN-01: La moto siempre cuesta 0 y no necesita consultar al repo
        return 0.0

class EstrategiaCobroCarro(EstrategiaCobro):
    def __init__(self, tarifa_repo: TarifaRepository, reloj: Reloj):
        self.tarifa_repo = tarifa_repo
        self.reloj = reloj

    def calcular_tarifa(self, primer_ingreso: datetime) -> float:
        # RN-05: La franja se determina por el primer ingreso del día
        franja = self.reloj.determinar_franja(primer_ingreso)
        tarifa = self.tarifa_repo.obtener_tarifa_activa("CARRO", franja)
        
        if tarifa is None:
            raise ValueError(f"No hay tarifa configurada para CARRO en la franja {franja}")
        
        return tarifa

# Contexto del Motor
class MotorCobro:
    def __init__(self, estrategia: EstrategiaCobro):
        self.estrategia = estrategia

    def liquidar(self, primer_ingreso: datetime) -> float:
        return self.estrategia.calcular_tarifa(primer_ingreso)