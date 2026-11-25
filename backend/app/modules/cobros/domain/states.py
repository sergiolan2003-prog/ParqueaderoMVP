from abc import ABC


class TransicionCobroInvalidaError(ValueError):
    pass


class EstadoCobro(ABC):
    codigo: str

    def confirmar_pago(self) -> "EstadoCobro":
        raise TransicionCobroInvalidaError(
            f"El cobro en estado {self.codigo} no permite registrar un pago."
        )

    def autoriza_salida(self, pase_vigente: bool) -> bool:
        return False


class CobroPendiente(EstadoCobro):
    codigo = "PENDIENTE"

    def confirmar_pago(self) -> EstadoCobro:
        return CobroPagado()


class CobroPagado(EstadoCobro):
    codigo = "PAGADO"

    def autoriza_salida(self, pase_vigente: bool) -> bool:
        return pase_vigente


class CobroAnulado(EstadoCobro):
    codigo = "ANULADO"


class CobroVencido(EstadoCobro):
    codigo = "VENCIDO"


_ESTADOS_COBRO: dict[str, type[EstadoCobro]] = {
    state.codigo: state
    for state in (CobroPendiente, CobroPagado, CobroAnulado, CobroVencido)
}


def estado_cobro(codigo: str) -> EstadoCobro:
    try:
        estado = _ESTADOS_COBRO[codigo]
    except KeyError as error:
        raise ValueError(f"Estado de cobro desconocido: {codigo}.") from error
    return estado()
