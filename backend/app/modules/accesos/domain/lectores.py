from dataclasses import dataclass
from random import Random
from string import ascii_uppercase
from typing import Protocol


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
