from datetime import date, datetime
from decimal import Decimal
from random import Random
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.config import settings
from app.core.database import get_db
from app.modules.accesos.application.entry import RegistrarEntradaUseCase
from app.modules.accesos.application.services import (
    ValidarSalidaVehiculoUseCase,
    vehiculo_en_parqueadero,
)
from app.modules.accesos.domain.exceptions import (
    CarrilNoEncontradoError,
    CarrilNoEsEntradaError,
    ConfianzaLPRInsuficienteError,
    CupoLlenoError,
    EventoAccesoDuplicadoError,
    ImagenDemasiadoGrandeError,
    IngresoRechazadoError,
    NombreImagenInvalidoError,
    SedeNoEncontradaError,
)
from app.modules.accesos.domain.factory import crear_lector_placa
from app.modules.accesos.domain.placa import PlacaInvalidaError
from app.modules.accesos.infrastructure.imagen import (
    eliminar_imagen,
    guardar_imagen,
    validar_imagen,
)
from app.modules.accesos.infrastructure.models import Carril, Sede
from app.modules.auth.api.dependencies import requiere_rol
from app.modules.auth.domain.entities import Rol
from app.modules.cobros.domain.motor_cobro import TarifaNoConfiguradaError
from app.modules.configuracion.application.services import (
    obtener_configuracion_operativa,
)

router = APIRouter(prefix="/accesos", tags=["Accesos"])
PLACA_COLOMBIANA_PATTERN = r"^(?:[A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z])$"


def _normalizar_placa_entrada(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper().replace(" ", "").replace("-", "")
    return value


class EntradaRequest(BaseModel):
    evento_id: UUID
    placa: str = Field(
        ...,
        pattern=PLACA_COLOMBIANA_PATTERN,
        json_schema_extra={"example": "ABC123"},
    )
    carril_id: UUID
    ocurrido_en: datetime
    confianza_lpr: float = Field(default=1.0, ge=0, le=1)
    lectura_manual: bool = False
    foto_url: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def normalizar_placa(cls, value: object) -> object:
        return _normalizar_placa_entrada(value)

    @field_validator("ocurrido_en")
    @classmethod
    def exigir_instante_con_zona(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ocurrido_en debe incluir zona horaria.")
        return value


class EntradaSimuladaRequest(BaseModel):
    carril_id: UUID = Field(..., description="Carril de entrada donde se registra.")
    evento_id: UUID = Field(
        default_factory=uuid4,
        description="Identificador idempotente del evento.",
    )
    ocurrido_en: datetime | None = Field(
        default=None,
        description="Instante de la lectura; si se omite, usa la hora actual.",
        examples=["2026-03-10T08:00:00-05:00"],
    )
    placa: str | None = Field(
        default=None,
        pattern=PLACA_COLOMBIANA_PATTERN,
        description="Placa opcional para controlar la salida del simulador.",
        examples=["ABC123"],
    )
    confianza_lpr: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Confianza opcional para controlar la salida del simulador.",
        examples=[0.99],
    )
    foto_url: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def normalizar_placa(cls, value: object) -> object:
        return _normalizar_placa_entrada(value)

    @field_validator("ocurrido_en")
    @classmethod
    def exigir_instante_con_zona(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("ocurrido_en debe incluir zona horaria.")
        return value


class EntradaResponse(BaseModel):
    evento_id: UUID
    placa: str
    carril_id: UUID
    ocurrido_en: datetime
    dia_operativo: date
    franja: str
    cobro_creado: bool
    cobro_id: UUID | None
    tarifa_id: UUID | None
    valor: Decimal | None
    pase_vigente: bool
    lectura_manual: bool
    confianza_lpr: float
    foto_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EntradaImagenResponse(BaseModel):
    evento_id: UUID | None = None
    placa: str
    carril_id: UUID
    ocurrido_en: datetime
    dia_operativo: date | None = None
    franja: str | None = None
    cobro_creado: bool = False
    cobro_id: UUID | None = None
    tarifa_id: UUID | None = None
    valor: Decimal | None = None
    pase_vigente: bool = False
    lectura_manual: bool = False
    confianza_lpr: float
    foto_url: str | None = None
    tipo_movimiento: str = "ENTRADA"
    barrera_abre: bool = True
    motivo: str | None = None


class SalidaRequest(BaseModel):
    placa: str = Field(
        ...,
        pattern=PLACA_COLOMBIANA_PATTERN,
        json_schema_extra={"example": "ABC123"},
    )
    carril_id: UUID
    foto_url: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def normalizar_placa(cls, value: object) -> object:
        return _normalizar_placa_entrada(value)


class SalidaResponse(BaseModel):
    placa: str
    carril_id: UUID
    barrera_abre: bool
    motivo: str
    registrado_en: datetime
    cobro_id: UUID | None = None
    valor: Decimal | None = None


class CarrilResponse(BaseModel):
    id: UUID
    sede_id: UUID
    sede_nombre: str
    sentido: str


def _http_error_ingreso(error: Exception) -> HTTPException:
    if isinstance(error, CupoLlenoError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{error.codigo}: {error.mensaje}",
        )
    if isinstance(error, (CarrilNoEncontradoError, SedeNoEncontradaError)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.mensaje,
        )
    if isinstance(error, CarrilNoEsEntradaError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.mensaje,
        )
    if isinstance(error, EventoAccesoDuplicadoError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{error.codigo}: {error.mensaje}",
        )
    if isinstance(error, TarifaNoConfiguradaError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
    if isinstance(error, PlacaInvalidaError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    if isinstance(error, ConfianzaLPRInsuficienteError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    if isinstance(error, ImagenDemasiadoGrandeError):
        return HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        )
    if isinstance(error, IngresoRechazadoError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    raise error


def _resolver_carril_salida(
    db: Session,
    sede_id: UUID,
    carril_salida_id: UUID | None,
) -> Carril:
    if carril_salida_id is not None:
        carril_salida = db.get(Carril, carril_salida_id)
        if carril_salida is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El carril de salida especificado no existe.",
            )
        if carril_salida.sentido != "SALIDA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El carril seleccionado no corresponde a un punto de salida.",
            )
        if carril_salida.sede_id != sede_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El carril de salida no pertenece a la sede seleccionada.",
            )
        return carril_salida

    carril_salida = (
        db.query(Carril)
        .filter(Carril.sede_id == sede_id, Carril.sentido == "SALIDA")
        .order_by(Carril.id)
        .first()
    )
    if carril_salida is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La sede no tiene un carril de salida configurado.",
        )
    return carril_salida


@router.get(
    "/carriles",
    response_model=list[CarrilResponse],
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def listar_carriles(
    db: Session = Depends(get_db),
) -> list[CarrilResponse]:
    filas = db.execute(
        select(Carril, Sede.nombre)
        .join(Sede, Carril.sede_id == Sede.id)
        .order_by(Carril.sentido, Sede.nombre, Carril.id)
    ).all()
    return [
        CarrilResponse(
            id=carril.id,
            sede_id=carril.sede_id,
            sede_nombre=sede_nombre,
            sentido=carril.sentido,
        )
        for carril, sede_nombre in filas
    ]


@router.post(
    "/entrada",
    response_model=EntradaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def registrar_entrada(
    payload: EntradaRequest,
    db: Session = Depends(get_db),
) -> EntradaResponse:
    configuracion = obtener_configuracion_operativa(db)
    try:
        resultado = RegistrarEntradaUseCase(
            db,
            confidence_threshold=configuracion.lpr_confidence_threshold,
            operating_periods=configuracion.operating_periods,
        ).ejecutar(
            evento_id=payload.evento_id,
            placa=payload.placa,
            carril_id=payload.carril_id,
            ocurrido_en=payload.ocurrido_en,
            confianza_lpr=payload.confianza_lpr,
            lectura_manual=payload.lectura_manual,
            foto_url=payload.foto_url,
        )
    except (
        CarrilNoEncontradoError,
        CarrilNoEsEntradaError,
        ConfianzaLPRInsuficienteError,
        EventoAccesoDuplicadoError,
        IngresoRechazadoError,
        PlacaInvalidaError,
        SedeNoEncontradaError,
        TarifaNoConfiguradaError,
        CupoLlenoError,
    ) as error:
        raise _http_error_ingreso(error) from error
    return EntradaResponse.model_validate(resultado)


@router.post(
    "/entrada/imagen",
    response_model=EntradaImagenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
async def registrar_entrada_por_imagen(
    response: Response,
    imagen: UploadFile = File(...),
    carril_id: UUID = Form(...),
    carril_salida_id: UUID | None = Form(default=None),
    placa_simulada: str | None = Form(default=None),
    confianza_simulada: float | None = Form(default=None, ge=0, le=1),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> EntradaImagenResponse:
    contenido = await imagen.read(settings.lpr_image_max_bytes + 1)
    if len(contenido) > settings.lpr_image_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"IMAGEN_DEMASIADO_GRANDE: La imagen supera el tamaño máximo "
                f"permitido de {settings.lpr_image_max_bytes} bytes."
            ),
        )

    try:
        extension = validar_imagen(contenido, imagen.content_type)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"ARCHIVO_NO_ES_IMAGEN: {error}",
        ) from error

    nombre_archivo = (imagen.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    lector = crear_lector_placa(
        "IMAGEN",
        nombre_archivo=nombre_archivo,
        placa=placa_simulada,
        confianza=confianza_simulada,
    )
    try:
        lectura = lector.leer()
    except (NombreImagenInvalidoError, PlacaInvalidaError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    configuracion = obtener_configuracion_operativa(db)
    if (
        lectura.confianza < configuracion.lpr_confidence_threshold
        and not lectura.lectura_manual
    ):
        raise _http_error_ingreso(ConfianzaLPRInsuficienteError())

    carril_entrada = db.get(Carril, carril_id)
    if carril_entrada is None:
        raise _http_error_ingreso(CarrilNoEncontradoError())
    if carril_entrada.sentido != "ENTRADA":
        raise _http_error_ingreso(CarrilNoEsEntradaError())

    foto_url = guardar_imagen(
        contenido,
        extension,
        settings.lpr_image_storage_path,
    )

    if vehiculo_en_parqueadero(db, lectura.placa, carril_entrada.sede_id):
        try:
            carril_salida = _resolver_carril_salida(
                db,
                carril_entrada.sede_id,
                carril_salida_id,
            )
            salida = ValidarSalidaVehiculoUseCase(db, clock).ejecutar(
                placa=lectura.placa,
                carril_id=carril_salida.id,
                foto_url=foto_url,
                confianza_lpr=lectura.confianza,
            )
        except Exception:
            eliminar_imagen(foto_url)
            raise

        if not salida["barrera_abre"]:
            eliminar_imagen(foto_url)
            foto_url_respuesta = None
        else:
            foto_url_respuesta = foto_url

        response.status_code = status.HTTP_200_OK
        return EntradaImagenResponse(
            placa=salida["placa"],
            carril_id=salida["carril_id"],
            ocurrido_en=salida["registrado_en"],
            cobro_creado=False,
            cobro_id=salida["cobro_id"],
            valor=salida["valor"],
            confianza_lpr=lectura.confianza,
            foto_url=foto_url_respuesta,
            tipo_movimiento="SALIDA",
            barrera_abre=salida["barrera_abre"],
            motivo=salida["motivo"],
        )

    try:
        resultado = RegistrarEntradaUseCase(
            db,
            clock=clock,
            confidence_threshold=configuracion.lpr_confidence_threshold,
            operating_periods=configuracion.operating_periods,
        ).ejecutar(
            evento_id=uuid4(),
            placa=lectura.placa,
            carril_id=carril_id,
            ocurrido_en=clock.now(),
            confianza_lpr=lectura.confianza,
            lectura_manual=lectura.lectura_manual,
            foto_url=foto_url,
        )
    except (
        CarrilNoEncontradoError,
        CarrilNoEsEntradaError,
        ConfianzaLPRInsuficienteError,
        EventoAccesoDuplicadoError,
        IngresoRechazadoError,
        PlacaInvalidaError,
        SedeNoEncontradaError,
        TarifaNoConfiguradaError,
        CupoLlenoError,
    ) as error:
        eliminar_imagen(foto_url)
        raise _http_error_ingreso(error) from error

    response.status_code = status.HTTP_201_CREATED
    return EntradaImagenResponse(
        evento_id=resultado.evento_id,
        placa=resultado.placa,
        carril_id=resultado.carril_id,
        ocurrido_en=resultado.ocurrido_en,
        dia_operativo=resultado.dia_operativo,
        franja=resultado.franja,
        cobro_creado=resultado.cobro_creado,
        cobro_id=resultado.cobro_id,
        tarifa_id=resultado.tarifa_id,
        valor=resultado.valor,
        pase_vigente=resultado.pase_vigente,
        lectura_manual=resultado.lectura_manual,
        confianza_lpr=resultado.confianza_lpr,
        foto_url=resultado.foto_url,
        tipo_movimiento="ENTRADA",
        barrera_abre=True,
        motivo=(
            f"Ingreso autorizado para {resultado.placa} con pase vigente."
            if resultado.pase_vigente
            else f"Ingreso registrado por imagen ({resultado.franja})."
        ),
    )


@router.post(
    "/entrada/simulada",
    response_model=EntradaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def registrar_entrada_simulada(
    payload: EntradaSimuladaRequest,
    db: Session = Depends(get_db),
) -> EntradaResponse:
    configuracion = obtener_configuracion_operativa(db)
    lector = crear_lector_placa(
        settings.lpr_reader_type,
        aleatorio=Random(),
        placa=payload.placa,
        confianza=payload.confianza_lpr,
    )
    try:
        resultado = RegistrarEntradaUseCase(
            db,
            confidence_threshold=configuracion.lpr_confidence_threshold,
            operating_periods=configuracion.operating_periods,
        ).ejecutar_con_lector(
            evento_id=payload.evento_id,
            carril_id=payload.carril_id,
            lector=lector,
            ocurrido_en=payload.ocurrido_en,
            foto_url=payload.foto_url,
        )
    except (
        CarrilNoEncontradoError,
        CarrilNoEsEntradaError,
        ConfianzaLPRInsuficienteError,
        EventoAccesoDuplicadoError,
        IngresoRechazadoError,
        PlacaInvalidaError,
        SedeNoEncontradaError,
        TarifaNoConfiguradaError,
        CupoLlenoError,
    ) as error:
        raise _http_error_ingreso(error) from error
    return EntradaResponse.model_validate(resultado)


@router.post(
    "/salida",
    response_model=SalidaResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(requiere_rol(Rol.OPERADOR))],
)
def validar_salida(
    payload: SalidaRequest,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> SalidaResponse:
    """
    HU-07 Salida: La barrera no abre con deuda.
    """
    caso_uso = ValidarSalidaVehiculoUseCase(db, clock)
    resultado = caso_uso.ejecutar(
        placa=payload.placa, carril_id=payload.carril_id, foto_url=payload.foto_url
    )
    return resultado
