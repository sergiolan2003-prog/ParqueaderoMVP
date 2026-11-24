from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class TarifaAplicable:
    id: UUID
    valor: Decimal


@dataclass(frozen=True)
class Liquidacion:
    tarifa: TarifaAplicable
    dia_operativo: date
    franja: str


class TarifaNoConfiguradaError(ValueError):
    def __init__(self, tipo_vehiculo: str, franja: str) -> None:
        self.tipo_vehiculo = tipo_vehiculo
        self.franja = franja
        super().__init__(
            f"No hay tarifa vigente configurada para {tipo_vehiculo} "
            f"en la franja {franja}."
        )


class TarifaRepository(Protocol):
    def obtener_tarifa_activa(
        self,
        sede_id: UUID,
        tipo_vehiculo: str,
        franja: str,
        dia_operativo: date,
    ) -> TarifaAplicable | None: ...


class Reloj(Protocol):
    def dia_operativo(self, instante: datetime | None = None) -> date: ...

    def franja(self, instante: datetime | None = None) -> str: ...


class EstrategiaCobro(ABC):
    @abstractmethod
    def liquidar(
        self,
        sede_id: UUID,
        tipo_vehiculo: str,
        primer_ingreso: datetime,
    ) -> Liquidacion:
        ...


class EstrategiaCobroConfigurada(EstrategiaCobro):
    def __init__(self, tarifa_repo: TarifaRepository, reloj: Reloj) -> None:
        self._tarifa_repo = tarifa_repo
        self._reloj = reloj

    def liquidar(
        self,
        sede_id: UUID,
        tipo_vehiculo: str,
        primer_ingreso: datetime,
    ) -> Liquidacion:
        dia_operativo = self._reloj.dia_operativo(primer_ingreso)
        franja = self._reloj.franja(primer_ingreso)
        tarifa = self._tarifa_repo.obtener_tarifa_activa(
            sede_id=sede_id,
            tipo_vehiculo=tipo_vehiculo,
            franja=franja,
            dia_operativo=dia_operativo,
        )
        if tarifa is None:
            raise TarifaNoConfiguradaError(tipo_vehiculo, franja)
        return Liquidacion(
            tarifa=tarifa,
            dia_operativo=dia_operativo,
            franja=franja,
        )


class MotorCobro:
    def __init__(self, estrategia: EstrategiaCobro) -> None:
        self._estrategia = estrategia

    def liquidar(
        self,
        sede_id: UUID,
        tipo_vehiculo: str,
        primer_ingreso: datetime,
    ) -> Liquidacion:
        return self._estrategia.liquidar(sede_id, tipo_vehiculo, primer_ingreso)
