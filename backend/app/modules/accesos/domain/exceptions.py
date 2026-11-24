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
