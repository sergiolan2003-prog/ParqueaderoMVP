# backend/app/modules/vehiculos/domain/placa.py
import re

class PlacaInvalidaError(ValueError):
    """Excepción de dominio para formatos de placa no reconocidos."""
    pass

class ClasificadorPlaca:
    @staticmethod
    def normalizar(placa: str) -> str:
        if not placa:
            raise PlacaInvalidaError("La placa no puede estar vacía")
        return placa.upper().replace(" ", "").replace("-", "")

    @staticmethod
    def clasificar(placa_raw: str) -> str:
        placa = ClasificadorPlaca.normalizar(placa_raw)
        
        # Regex para CARRO: 3 letras seguidas de 3 números
        if re.match(r"^[A-Z]{3}\d{3}$", placa):
            return "CARRO"
        
        # Regex para MOTO: 3 letras, 2 números y 1 letra
        elif re.match(r"^[A-Z]{3}\d{2}[A-Z]$", placa):
            return "MOTO"
        
        else:
            raise PlacaInvalidaError(f"Formato de placa inválido: {placa}")