class PagoDuplicadoError(Exception):
    """La referencia del pago ya fue registrada."""


class PagoCobroDuplicadoError(Exception):
    """El cobro ya tiene un pago registrado."""


class CobroNoEncontradoError(Exception):
    """No existe el cobro solicitado."""


class CobroYaPagadoError(Exception):
    """El cobro ya fue pagado con otra referencia."""


class ReferenciaPagoEnUsoError(Exception):
    """La referencia de pago pertenece a otro cobro."""


class PagoNoPermitidoError(Exception):
    """El estado o valor del cobro no permite el pago."""


class PaseNoEncontradoError(Exception):
    """El pago confirmado no tiene el pase asociado esperado."""
