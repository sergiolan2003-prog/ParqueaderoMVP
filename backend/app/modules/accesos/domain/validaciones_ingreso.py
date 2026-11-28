from dataclasses import dataclass
from typing import Protocol

from app.modules.accesos.domain.exceptions import (
    ConfianzaLPRInsuficienteError,
    CupoLlenoError,
)


@dataclass(frozen=True)
class ContextoValidacionIngreso:
    confianza_lpr: float
    umbral_confianza: float
    lectura_manual: bool
    pase_vigente: bool
    tipo_vehiculo: str = ""
    ocupacion_actual: int = 0
    cupo_maximo: int = 1


class ValidadorIngreso(Protocol):
    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        """Valida un aspecto del ingreso."""


class CadenaValidacionIngreso:
    def __init__(self, validadores: tuple[ValidadorIngreso, ...]) -> None:
        self._validadores = validadores

    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        for validador in self._validadores:
            validador.validar(contexto)


class ValidadorConfianza:
    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        if (
            contexto.confianza_lpr < contexto.umbral_confianza
            and not contexto.lectura_manual
        ):
            raise ConfianzaLPRInsuficienteError()


class ValidadorCupo:
    """Valida si hay cupo disponible para el tipo de vehículo; si no, marca LLENO."""

    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        sin_cupo_configurado = contexto.cupo_maximo <= 0
        cupo_alcanzado = contexto.ocupacion_actual >= contexto.cupo_maximo
        if sin_cupo_configurado or cupo_alcanzado:
            raise CupoLlenoError(contexto.tipo_vehiculo or "VEHICULO")


class ValidadorPaseVigente:
    """Recibe el estado del pase; HU-06 no rechaza el ingreso por este motivo."""

    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        return None
