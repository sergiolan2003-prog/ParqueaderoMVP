from dataclasses import dataclass
from typing import Protocol

from app.modules.accesos.domain.exceptions import ConfianzaLPRInsuficienteError


@dataclass(frozen=True)
class ContextoValidacionIngreso:
    confianza_lpr: float
    umbral_confianza: float
    lectura_manual: bool
    pase_vigente: bool


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
    """No rechaza ingresos hasta que HU-13 implemente la validación de cupos."""

    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        return None


class ValidadorPaseVigente:
    """Recibe el estado del pase; HU-06 no rechaza el ingreso por este motivo."""

    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        return None
