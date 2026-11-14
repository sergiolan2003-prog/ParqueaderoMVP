from datetime import datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.accesos.infrastructure import constraints


class Sede(Base):
    __tablename__ = "sede"
    __table_args__ = (
        UniqueConstraint("nombre", name=constraints.SEDE_NOMBRE_UNIQUE),
        CheckConstraint(
            "cupos_carro >= 0",
            name=constraints.SEDE_CUPOS_CARRO_NONNEGATIVE,
        ),
        CheckConstraint(
            "cupos_moto >= 0",
            name=constraints.SEDE_CUPOS_MOTO_NONNEGATIVE,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    zona_horaria: Mapped[str] = mapped_column(String, nullable=False)
    inicio_dia_operativo: Mapped[time] = mapped_column(Time, nullable=False)
    cupos_carro: Mapped[int] = mapped_column(Integer, nullable=False)
    cupos_moto: Mapped[int] = mapped_column(Integer, nullable=False)


class Carril(Base):
    __tablename__ = "carril"
    __table_args__ = (
        CheckConstraint(
            "sentido IN ('ENTRADA', 'SALIDA')",
            name=constraints.CARRIL_SENTIDO_VALID,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    sede_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("sede.id"),
        nullable=False,
    )
    sentido: Mapped[str] = mapped_column(String, nullable=False)


class Vehiculo(Base):
    __tablename__ = "vehiculo"
    __table_args__ = (
        CheckConstraint(
            "placa = upper(placa)",
            name=constraints.VEHICULO_PLACA_UPPERCASE,
        ),
        CheckConstraint(
            "tipo IN ('CARRO', 'MOTO')",
            name=constraints.VEHICULO_TIPO_VALID,
        ),
    )

    placa: Mapped[str] = mapped_column(String, primary_key=True)
    tipo: Mapped[str] = mapped_column(String, nullable=False)


class EventoAcceso(Base):
    __tablename__ = "evento_acceso"
    __table_args__ = (
        CheckConstraint(
            "confianza_lpr >= 0 AND confianza_lpr <= 1",
            name=constraints.EVENTO_CONFIANZA_RANGE,
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    placa: Mapped[str] = mapped_column(
        String,
        ForeignKey("vehiculo.placa"),
        nullable=False,
    )
    carril_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("carril.id"),
        nullable=False,
    )
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    confianza_lpr: Mapped[float] = mapped_column(Float, nullable=False)
    lectura_manual: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    foto_url: Mapped[str | None] = mapped_column(String, nullable=True)
