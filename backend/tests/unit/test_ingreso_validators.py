import pytest

from app.modules.accesos.domain.exceptions import ConfianzaLPRInsuficienteError
from app.modules.accesos.domain.validaciones_ingreso import (
    CadenaValidacionIngreso,
    ContextoValidacionIngreso,
    ValidadorConfianza,
    ValidadorCupo,
    ValidadorPaseVigente,
)


def _contexto(
    confianza_lpr: float = 0.9,
    umbral_confianza: float = 0.8,
    lectura_manual: bool = False,
    pase_vigente: bool = False,
) -> ContextoValidacionIngreso:
    return ContextoValidacionIngreso(
        confianza_lpr=confianza_lpr,
        umbral_confianza=umbral_confianza,
        lectura_manual=lectura_manual,
        pase_vigente=pase_vigente,
    )


class _ValidadorDePrueba:
    def __init__(
        self,
        nombre: str,
        ejecuciones: list[str],
        error: Exception | None = None,
    ) -> None:
        self._nombre = nombre
        self._ejecuciones = ejecuciones
        self._error = error

    def validar(self, contexto: ContextoValidacionIngreso) -> None:
        self._ejecuciones.append(self._nombre)
        if self._error is not None:
            raise self._error


def test_chain_runs_validators_in_order() -> None:
    ejecuciones: list[str] = []
    cadena = CadenaValidacionIngreso(
        (
            _ValidadorDePrueba("confianza", ejecuciones),
            _ValidadorDePrueba("cupo", ejecuciones),
            _ValidadorDePrueba("pase", ejecuciones),
        )
    )

    cadena.validar(_contexto())

    assert ejecuciones == ["confianza", "cupo", "pase"]


def test_chain_stops_at_first_rejection() -> None:
    ejecuciones: list[str] = []
    rechazo = ConfianzaLPRInsuficienteError()
    cadena = CadenaValidacionIngreso(
        (
            _ValidadorDePrueba("confianza", ejecuciones, rechazo),
            _ValidadorDePrueba("cupo", ejecuciones),
        )
    )

    with pytest.raises(ConfianzaLPRInsuficienteError):
        cadena.validar(_contexto())

    assert ejecuciones == ["confianza"]


def test_removing_a_validator_keeps_remaining_validators_independent() -> None:
    ejecuciones: list[str] = []
    cadena = CadenaValidacionIngreso(
        (
            _ValidadorDePrueba("confianza", ejecuciones),
            _ValidadorDePrueba("pase", ejecuciones),
        )
    )

    cadena.validar(_contexto())

    assert ejecuciones == ["confianza", "pase"]


def test_minimal_capacity_and_pass_validators_do_not_reject() -> None:
    contexto = _contexto(pase_vigente=True)

    ValidadorCupo().validar(contexto)
    ValidadorPaseVigente().validar(contexto)


def test_confidence_validator_rejects_low_confidence_unless_manual() -> None:
    validador = ValidadorConfianza()

    with pytest.raises(ConfianzaLPRInsuficienteError):
        validador.validar(_contexto(confianza_lpr=0.79))

    validador.validar(_contexto(confianza_lpr=0.0, lectura_manual=True))
