import re
from dataclasses import dataclass
from random import Random
from string import ascii_uppercase
from typing import Protocol

from app.modules.accesos.domain.exceptions import NombreImagenInvalidoError
from app.modules.accesos.domain.placa import ClasificadorPlaca


@dataclass(frozen=True)
class LecturaPlaca:
    placa: str
    confianza: float
    lectura_manual: bool = False


class LectorPlaca(Protocol):
    def leer(self) -> LecturaPlaca:
        """Obtiene una lectura de placa intercambiable."""


class LectorSimulado:
    def __init__(
        self,
        aleatorio: Random,
        placa: str | None = None,
        confianza: float | None = None,
    ) -> None:
        self._aleatorio = aleatorio
        self._placa = placa
        self._confianza = confianza

    def leer(self) -> LecturaPlaca:
        placa = self._placa if self._placa is not None else self._generar_placa()
        confianza = (
            self._confianza
            if self._confianza is not None
            else self._aleatorio.random()
        )
        return LecturaPlaca(placa=placa, confianza=confianza)

    def _generar_placa(self) -> str:
        letras = "".join(self._aleatorio.choice(ascii_uppercase) for _ in range(3))
        if self._aleatorio.choice((True, False)):
            return f"{letras}{self._aleatorio.randrange(1000):03d}"
        return (
            f"{letras}{self._aleatorio.randrange(100):02d}"
            f"{self._aleatorio.choice(ascii_uppercase)}"
        )


class LectorManual:
    def __init__(self, placa: str) -> None:
        self._placa = placa

    def leer(self) -> LecturaPlaca:
        return LecturaPlaca(
            placa=self._placa,
            confianza=1.0,
            lectura_manual=True,
        )


class LectorImagenSimulado:
    def __init__(
        self,
        nombre_archivo: str,
        placa_simulada: str | None = None,
        confianza_simulada: float | None = None,
    ) -> None:
        self._nombre_archivo = nombre_archivo
        self._placa_simulada = placa_simulada
        self._confianza_simulada = confianza_simulada

    def leer(self) -> LecturaPlaca:
        coincidencia = re.fullmatch(
            r"([A-Za-z0-9 -]+)_([0-9]+(?:\.[0-9]+)?)\.([A-Za-z0-9]+)",
            self._nombre_archivo,
        )
        if coincidencia is None:
            raise NombreImagenInvalidoError()

        placa_bruta = (
            self._placa_simulada
            if self._placa_simulada is not None
            else coincidencia.group(1)
        )
        confianza = (
            self._confianza_simulada
            if self._confianza_simulada is not None
            else float(coincidencia.group(2))
        )
        placa = ClasificadorPlaca.normalizar(placa_bruta)
        ClasificadorPlaca.clasificar(placa)
        if not 0 <= confianza <= 1:
            raise NombreImagenInvalidoError()
        return LecturaPlaca(placa=placa, confianza=confianza)
