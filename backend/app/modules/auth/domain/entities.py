from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class Rol(str, Enum):
    OPERADOR = "OPERADOR"
    ADMINISTRADOR = "ADMINISTRADOR"


@dataclass(frozen=True)
class Usuario:
    id: UUID
    username: str
    password_hash: str
    rol: Rol
    activo: bool


@dataclass(frozen=True)
class IdentidadAutenticada:
    username: str
    rol: Rol
