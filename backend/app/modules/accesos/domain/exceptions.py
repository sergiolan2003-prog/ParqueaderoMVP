class IngresoRechazadoError(Exception):
    def __init__(self, codigo: str, mensaje: str) -> None:
        self.codigo = codigo
        self.mensaje = mensaje
        super().__init__(f"{codigo}: {mensaje}")


class ConfianzaLPRInsuficienteError(IngresoRechazadoError):
    def __init__(self) -> None:
        super().__init__(
            "CONFIANZA_LPR_INSUFICIENTE",
            "La confianza de la lectura LPR no alcanza el umbral requerido.",
        )


class CarrilNoEncontradoError(IngresoRechazadoError):
    def __init__(self) -> None:
        super().__init__(
            "CARRIL_NO_ENCONTRADO",
            "El carril especificado no existe.",
        )


class CarrilNoEsEntradaError(IngresoRechazadoError):
    def __init__(self) -> None:
        super().__init__(
            "CARRIL_NO_ES_ENTRADA",
            "El carril seleccionado no corresponde a un punto de entrada.",
        )


class SedeNoEncontradaError(IngresoRechazadoError):
    def __init__(self) -> None:
        super().__init__(
            "SEDE_NO_ENCONTRADA",
            "La sede asociada al carril no existe.",
        )


class EventoAccesoDuplicadoError(IngresoRechazadoError):
    def __init__(self) -> None:
        super().__init__(
            "EVENTO_DUPLICADO",
            "El evento de acceso ya fue registrado.",
        )
