from random import Random

from app.modules.accesos.domain.lectores import (
    LectorImagenSimulado,
    LectorManual,
    LectorPlaca,
    LectorSimulado,
)


def crear_lector_placa(
    tipo: str,
    *,
    aleatorio: Random | None = None,
    placa: str | None = None,
    confianza: float | None = None,
    nombre_archivo: str | None = None,
) -> LectorPlaca:
    tipo_normalizado = tipo.upper()
    if tipo_normalizado == "MANUAL":
        if placa is None:
            raise ValueError("La fábrica requiere una placa para el lector manual.")
        return LectorManual(placa)
    if tipo_normalizado == "IMAGEN":
        if nombre_archivo is None:
            raise ValueError(
                "La fábrica requiere el nombre de archivo para el lector de imagen."
            )
        return LectorImagenSimulado(
            nombre_archivo=nombre_archivo,
            placa_simulada=placa,
            confianza_simulada=confianza,
        )
    return LectorSimulado(
        aleatorio=aleatorio or Random(),
        placa=placa,
        confianza=confianza,
    )
