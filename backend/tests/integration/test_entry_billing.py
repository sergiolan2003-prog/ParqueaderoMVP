from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from decimal import Decimal
from random import Random
from threading import Barrier
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import FixedClock
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.accesos.application.entry import RegistrarEntradaUseCase
from app.modules.accesos.application.services import ValidarSalidaVehiculoUseCase
from app.modules.accesos.domain.lectores import LectorManual, LectorSimulado
from app.modules.accesos.infrastructure.models import (
    Carril,
    EventoAcceso,
    Sede,
    Vehiculo,
)
from app.modules.auth.infrastructure.seed import seed_users
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.pagos.application.services import RegistrarPagoEfectivoUseCase
from app.modules.pagos.infrastructure.models import Pago
from app.modules.pases.infrastructure.models import Pase
from app.modules.tarifas.infrastructure.models import Tarifa

LOCAL_ZONE = ZoneInfo("America/Bogota")


@pytest.fixture
def operator_client(db_session: Session) -> Iterator[tuple[TestClient, dict[str, str]]]:
    seed_users(db_session)

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            data={
                "username": settings.seed_operador_username,
                "password": settings.seed_operador_password,
            },
        )
        assert login.status_code == 200
        yield client, {"Authorization": f"Bearer {login.json()['access_token']}"}
    app.dependency_overrides.clear()


def _new_sede(session: Session, name: str) -> tuple[Sede, Carril]:
    sede = Sede(
        nombre=f"{name}-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(6),
        cupos_carro=50,
        cupos_moto=50,
    )
    session.add(sede)
    session.flush()
    carril = Carril(sede_id=sede.id, sentido="ENTRADA")
    session.add(carril)
    session.flush()
    return sede, carril


def _new_exit_lane(session: Session, sede: Sede) -> Carril:
    lane = Carril(sede_id=sede.id, sentido="SALIDA")
    session.add(lane)
    session.flush()
    return lane


@pytest.fixture
def prepare_paid_pass(
    db_session: Session,
) -> Callable[[Cobro, datetime], Pase]:
    """Pay through HU-11 and return the generated pass."""

    def prepare(cobro: Cobro, starts_at: datetime) -> Pase:
        result = RegistrarPagoEfectivoUseCase(
            db_session,
            clock=FixedClock(starts_at),
        ).ejecutar(
            cobro_id=cobro.id,
            referencia_pago=f"hu10-{uuid4()}",
        )
        pase = db_session.get(Pase, result.pase_id)
        assert pase is not None
        return pase

    return prepare


def _add_tarifa(
    session: Session,
    sede: Sede,
    tipo_vehiculo: str,
    franja: str,
    valor: Decimal,
) -> Tarifa:
    tarifa = Tarifa(
        sede_id=sede.id,
        tipo_vehiculo=tipo_vehiculo,
        franja=franja,
        valor=valor,
        vigente_desde=date(2026, 1, 1),
    )
    session.add(tarifa)
    session.flush()
    return tarifa


def _add_standard_tariffs(session: Session, sede: Sede) -> dict[str, Tarifa]:
    tarifas = {
        "day": _add_tarifa(
            session, sede, "CARRO", "DIURNA", Decimal("12000.00")
        ),
        "night": _add_tarifa(
            session, sede, "CARRO", "NOCTURNA", Decimal("8000.00")
        ),
        "moto_day": _add_tarifa(
            session, sede, "MOTO", "DIURNA", Decimal("0.00")
        ),
        "moto_night": _add_tarifa(
            session, sede, "MOTO", "NOCTURNA", Decimal("0.00")
        ),
    }
    return tarifas


def _entry(
    client: TestClient,
    headers: dict[str, str],
    lane: Carril,
    plate: str,
    when: datetime,
    event_id: UUID | None = None,
    confidence: float = 0.99,
    manual: bool = False,
) -> object:
    event_id = event_id or uuid4()
    return client.post(
        "/accesos/entrada",
        headers=headers,
        json={
            "evento_id": str(event_id),
            "placa": plate,
            "carril_id": str(lane.id),
            "ocurrido_en": when.isoformat(),
            "confianza_lpr": confidence,
            "lectura_manual": manual,
        },
    )


def _entry_counts(
    session: Session,
    placa: str,
    evento_id: UUID,
) -> tuple[int, int, int]:
    return (
        session.query(func.count(Vehiculo.placa))
        .filter(Vehiculo.placa == placa)
        .scalar(),
        session.query(func.count(EventoAcceso.id))
        .filter(EventoAcceso.id == evento_id)
        .scalar(),
        session.query(func.count(Cobro.id)).filter(Cobro.placa == placa).scalar(),
    )


@pytest.mark.parametrize(
    ("hour", "minute", "expected_period", "expected_value"),
    [
        (8, 0, "DIURNA", Decimal("12000.00")),
        (19, 0, "NOCTURNA", Decimal("8000.00")),
    ],
)
def test_car_entry_creates_pending_charge_at_first_entry_rate(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
    hour: int,
    minute: int,
    expected_period: str,
    expected_value: Decimal,
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Ingreso")
    tariffs = _add_standard_tariffs(db_session, sede)
    event_id = uuid4()
    response = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, hour, minute, tzinfo=LOCAL_ZONE),
        event_id,
    )

    assert response.status_code == 201
    result = response.json()
    assert result["evento_id"] == str(event_id)
    assert db_session.get(EventoAcceso, event_id) is not None
    assert result["franja"] == expected_period
    assert result["cobro_creado"] is True, result
    assert Decimal(result["valor"]) == expected_value
    expected_tarifa = tariffs["day" if expected_period == "DIURNA" else "night"]
    assert result["tarifa_id"] == str(expected_tarifa.id)
    assert result["dia_operativo"] == "2026-03-10"
    assert db_session.get(Cobro, UUID(result["cobro_id"])).estado == "PENDIENTE"
    if expected_period == "NOCTURNA":
        assert tariffs["night"].valor < tariffs["day"].valor


def test_motor_configured_zero_for_motorcycle_does_not_create_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Moto")
    tariffs = _add_standard_tariffs(db_session, sede)

    response = _entry(
        client,
        headers,
        lane,
        "ABC12D",
        datetime(2026, 3, 10, 10, 0, tzinfo=LOCAL_ZONE),
    )

    assert response.status_code == 201
    assert response.json()["cobro_creado"] is False
    assert response.json()["tarifa_id"] == str(tariffs["moto_day"].id)
    assert Decimal(response.json()["valor"]) == Decimal("0.00")
    assert db_session.query(Cobro).filter(Cobro.sede_id == sede.id).count() == 0


def test_current_pass_prevents_charge_on_reentry(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Pase")
    vehicle = Vehiculo(placa="ABC123", tipo="CARRO")
    db_session.add(vehicle)
    db_session.flush()
    db_session.add(
        Pase(
            placa=vehicle.placa,
            sede_id=sede.id,
            vigente_desde=datetime(2026, 3, 10, 20, 0, tzinfo=LOCAL_ZONE),
            vigente_hasta=datetime(2026, 3, 10, 23, 0, tzinfo=LOCAL_ZONE),
        )
    )
    db_session.flush()

    response = _entry(
        client,
        headers,
        lane,
        vehicle.placa,
        datetime(2026, 3, 10, 22, 0, tzinfo=LOCAL_ZONE),
    )

    assert response.status_code == 201
    assert response.json()["pase_vigente"] is True
    assert response.json()["cobro_creado"] is False
    assert db_session.query(Cobro).filter(Cobro.sede_id == sede.id).count() == 0
    assert db_session.query(Tarifa).filter(Tarifa.sede_id == sede.id).count() == 0


def test_new_operating_day_after_0550_creates_a_new_daytime_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "CambioDia")
    tarifas = _add_standard_tariffs(db_session, sede)

    previous_day = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 5, 50, tzinfo=LOCAL_ZONE),
    )
    next_day = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 9, 0, tzinfo=LOCAL_ZONE),
    )

    assert previous_day.status_code == 201
    assert previous_day.json()["dia_operativo"] == "2026-03-09"
    assert previous_day.json()["franja"] == "NOCTURNA"
    assert next_day.status_code == 201
    assert next_day.json()["dia_operativo"] == "2026-03-10"
    assert next_day.json()["franja"] == "DIURNA"
    assert next_day.json()["cobro_creado"] is True, next_day.json()
    assert next_day.json()["tarifa_id"] == str(tarifas["day"].id)
    assert Decimal(next_day.json()["valor"]) == Decimal("12000.00")
    assert next_day.json()["cobro_id"] != previous_day.json()["cobro_id"]
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == "ABC123", Cobro.sede_id == sede.id)
        .count()
        == 2
    )


def test_missing_tariff_rejects_entry_without_zero_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "SinTarifa")

    response = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE),
    )

    assert response.status_code == 409
    assert "No hay tarifa vigente configurada" in response.json()["detail"]
    assert db_session.query(Cobro).filter(Cobro.sede_id == sede.id).count() == 0


def test_low_confidence_rejects_entry_without_partial_records(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    _, lane = _new_sede(db_session, "Confianza")
    event_id = uuid4()

    response = client.post(
        "/accesos/entrada",
        headers=headers,
        json={
            "evento_id": str(event_id),
            "placa": "ABC123",
            "carril_id": str(lane.id),
            "ocurrido_en": datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE).isoformat(),
            "confianza_lpr": 0.2,
        },
    )

    assert response.status_code == 422
    assert "CONFIANZA_LPR_INSUFICIENTE" in response.json()["detail"]
    assert db_session.get(Vehiculo, "ABC123") is None
    assert db_session.get(EventoAcceso, event_id) is None
    assert _entry_counts(db_session, "ABC123", event_id) == (0, 0, 0)


def test_duplicate_event_id_returns_conflict_without_partial_records(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Duplicado")
    _add_standard_tariffs(db_session, sede)
    event_id = uuid4()
    when = datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE)
    first = _entry(client, headers, lane, "ABC123", when, event_id)
    counts_before_duplicate = _entry_counts(db_session, "DEF456", event_id)
    assert counts_before_duplicate == (0, 1, 0)

    response = _entry(client, headers, lane, "DEF456", when, event_id)

    assert first.status_code == 201
    assert response.status_code == 409
    assert "EVENTO_DUPLICADO" in response.json()["detail"]
    assert db_session.get(Vehiculo, "DEF456") is None
    assert _entry_counts(db_session, "DEF456", event_id) == counts_before_duplicate


def test_invalid_plate_does_not_create_partial_records(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    _, lane = _new_sede(db_session, "PlacaInvalida")
    event_id = uuid4()

    response = _entry(
        client,
        headers,
        lane,
        "INVALIDA",
        datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE),
        event_id,
    )

    assert response.status_code == 422
    assert db_session.get(Vehiculo, "INVALIDA") is None
    assert db_session.get(EventoAcceso, event_id) is None
    assert _entry_counts(db_session, "INVALIDA", event_id) == (0, 0, 0)


def test_simulated_entry_requires_operator_and_documents_openapi_schema(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Simulada")
    _add_standard_tariffs(db_session, sede)
    payload = {
        "carril_id": str(lane.id),
        "placa": "ABC123",
        "confianza_lpr": 0.99,
    }
    entry_payload = {
        "evento_id": str(uuid4()),
        "placa": "ABC123",
        "carril_id": str(lane.id),
        "ocurrido_en": datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE).isoformat(),
    }

    admin_login = client.post(
        "/auth/login",
        data={
            "username": settings.seed_admin_username,
            "password": settings.seed_admin_password,
        },
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    for path, body in (
        ("/accesos/entrada/simulada", payload),
        ("/accesos/entrada", entry_payload),
    ):
        unauthenticated = client.post(path, json=body)
        assert unauthenticated.status_code == 401

        forbidden = client.post(path, headers=admin_headers, json=body)
        assert forbidden.status_code == 403

    response = client.post(
        "/accesos/entrada/simulada",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["placa"] == "ABC123"

    openapi = client.get("/openapi.json").json()
    simulated_schema = openapi["components"]["schemas"]["EntradaSimuladaRequest"]
    assert "examples" in simulated_schema["properties"]["placa"]
    assert "examples" in simulated_schema["properties"]["confianza_lpr"]


def test_entry_use_case_accepts_interchangeable_readers(
    db_session: Session,
) -> None:
    sede, lane = _new_sede(db_session, "Lectores")
    _add_standard_tariffs(db_session, sede)
    use_case = RegistrarEntradaUseCase(db_session, confidence_threshold=0.8)
    when = datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE)

    manual = use_case.ejecutar_con_lector(
        evento_id=uuid4(),
        carril_id=lane.id,
        lector=LectorManual("ABC123"),
        ocurrido_en=when,
    )
    simulated = use_case.ejecutar_con_lector(
        evento_id=uuid4(),
        carril_id=lane.id,
        lector=LectorSimulado(
            Random(1),
            placa="DEF456",
            confianza=0.99,
        ),
        ocurrido_en=when,
    )

    assert manual.placa == "ABC123"
    assert simulated.placa == "DEF456"
    assert db_session.get(EventoAcceso, manual.evento_id).lectura_manual is True
    assert db_session.get(EventoAcceso, simulated.evento_id).lectura_manual is False


def test_reentry_without_pass_reuses_same_operating_day_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, lane = _new_sede(db_session, "Reingreso")
    _add_standard_tariffs(db_session, sede)
    first = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE),
    )
    second = _entry(
        client,
        headers,
        lane,
        "ABC123",
        datetime(2026, 3, 10, 22, 0, tzinfo=LOCAL_ZONE),
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["cobro_creado"] is True, first.json()
    assert second.json()["cobro_creado"] is False
    assert second.json()["cobro_id"] == first.json()["cobro_id"]
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == "ABC123", Cobro.sede_id == sede.id)
        .count()
        == 1
    )


def test_concurrent_charge_inserts_leave_one_charge(
    database_engine,
) -> None:
    sessions = sessionmaker(bind=database_engine)
    random_value = uuid4().int
    letras = "".join(
        chr(ord("A") + ((random_value >> (position * 5)) % 26))
        for position in range(3)
    )
    placa = f"{letras}{random_value % 1000:03d}"
    sede_id = uuid4()
    carril_id = uuid4()
    instante = datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE)

    with sessions.begin() as session:
        sede = Sede(
            id=sede_id,
            nombre=f"Concurrente-{uuid4()}",
            zona_horaria="America/Bogota",
            inicio_dia_operativo=time(6),
            cupos_carro=10,
            cupos_moto=10,
        )
        carril = Carril(
            id=carril_id,
            sede_id=sede_id,
            sentido="ENTRADA",
        )
        tarifa = Tarifa(
            sede_id=sede_id,
            tipo_vehiculo="CARRO",
            franja="DIURNA",
            valor=Decimal("12000.00"),
            vigente_desde=date(2026, 1, 1),
        )
        session.add(sede)
        session.flush()
        session.add_all([carril, tarifa])

    barrier = Barrier(2)

    def register_entry() -> bool:
        with sessions() as session:
            barrier.wait(timeout=10)
            result = RegistrarEntradaUseCase(session).ejecutar(
                evento_id=uuid4(),
                placa=placa,
                carril_id=carril_id,
                ocurrido_en=instante,
            )
            return result.cobro_creado

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: register_entry(), range(2)))

    with sessions() as session:
        charge_count = (
            session.query(func.count(Cobro.id))
            .filter(
                Cobro.placa == placa,
                Cobro.sede_id == sede_id,
                Cobro.dia_operativo == date(2026, 3, 10),
            )
            .scalar()
        )
        event_count = (
            session.query(func.count(EventoAcceso.id))
            .filter(EventoAcceso.placa == placa)
            .scalar()
        )

    assert sorted(results) == [False, True]
    assert charge_count == 1
    assert event_count == 2


def test_scenario_1_motorcycle_entry_and_exit_are_recorded_without_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "Escenario1")
    exit_lane = _new_exit_lane(db_session, sede)
    tariffs = _add_standard_tariffs(db_session, sede)
    entry_at = datetime(2026, 3, 10, 10, 0, tzinfo=LOCAL_ZONE)

    entry = _entry(client, headers, entry_lane, "ABC12D", entry_at)
    exit_result = ValidarSalidaVehiculoUseCase(
        db_session,
        clock=FixedClock(datetime(2026, 3, 10, 14, 0, tzinfo=LOCAL_ZONE)),
    ).ejecutar("ABC12D", exit_lane.id)

    assert entry.status_code == 201
    assert entry.json()["cobro_creado"] is False
    assert entry.json()["tarifa_id"] == str(tariffs["moto_day"].id)
    assert exit_result["barrera_abre"] is True
    assert (
        db_session.query(EventoAcceso)
        .filter(EventoAcceso.placa == "ABC12D")
        .count()
        == 2
    )
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == "ABC12D", Cobro.sede_id == sede.id)
        .count()
        == 0
    )


def test_scenario_3_and_4_paid_car_reenters_without_a_second_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
    prepare_paid_pass: Callable[[Cobro, datetime], Pase],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "Escenarios34")
    exit_lane = _new_exit_lane(db_session, sede)
    _add_standard_tariffs(db_session, sede)
    plate = "ABC123"
    first_entry_at = datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE)
    first_entry = _entry(client, headers, entry_lane, plate, first_entry_at)
    assert first_entry.status_code == 201
    cobro = db_session.get(Cobro, UUID(first_entry.json()["cobro_id"]))
    assert cobro is not None
    prepare_paid_pass(cobro, first_entry_at)

    exit_result = ValidarSalidaVehiculoUseCase(
        db_session,
        clock=FixedClock(datetime(2026, 3, 10, 12, 0, tzinfo=LOCAL_ZONE)),
    ).ejecutar(plate, exit_lane.id)
    reentry_15 = _entry(
        client,
        headers,
        entry_lane,
        plate,
        datetime(2026, 3, 10, 15, 0, tzinfo=LOCAL_ZONE),
    )
    reentry_22 = _entry(
        client,
        headers,
        entry_lane,
        plate,
        datetime(2026, 3, 10, 22, 0, tzinfo=LOCAL_ZONE),
    )

    assert exit_result["barrera_abre"] is True
    assert reentry_15.status_code == 201
    assert reentry_15.json()["pase_vigente"] is True
    assert reentry_15.json()["cobro_creado"] is False
    assert reentry_22.status_code == 201
    assert reentry_22.json()["pase_vigente"] is True
    assert reentry_22.json()["cobro_creado"] is False
    assert (
        db_session.query(EventoAcceso)
        .filter(EventoAcceso.placa == plate)
        .count()
        == 4
    )
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == plate, Cobro.sede_id == sede.id)
        .count()
        == 1
    )


def test_scenario_6_late_night_entry_and_early_exit_keep_one_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
    prepare_paid_pass: Callable[[Cobro, datetime], Pase],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "Escenario6")
    exit_lane = _new_exit_lane(db_session, sede)
    _add_standard_tariffs(db_session, sede)
    entry_at = datetime(2026, 3, 10, 23, 0, tzinfo=LOCAL_ZONE)
    entry = _entry(client, headers, entry_lane, "ABC123", entry_at)
    assert entry.status_code == 201
    assert entry.json()["dia_operativo"] == "2026-03-10"
    assert entry.json()["franja"] == "NOCTURNA"

    cobro = db_session.get(Cobro, UUID(entry.json()["cobro_id"]))
    assert cobro is not None
    prepare_paid_pass(cobro, entry_at)
    exit_result = ValidarSalidaVehiculoUseCase(
        db_session,
        clock=FixedClock(datetime(2026, 3, 11, 1, 0, tzinfo=LOCAL_ZONE)),
    ).ejecutar("ABC123", exit_lane.id)

    assert exit_result["barrera_abre"] is True
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == "ABC123", Cobro.sede_id == sede.id)
        .count()
        == 1
    )
    assert (
        db_session.query(EventoAcceso)
        .filter(EventoAcceso.placa == "ABC123")
        .count()
        == 2
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Depende de HU-19 (S-05): no hay cobro automático "
        "al cambiar el día con el vehículo adentro."
    ),
)
def test_scenario_7_generates_daytime_charge_while_vehicle_stays_inside(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
    prepare_paid_pass: Callable[[Cobro, datetime], Pase],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "Escenario7")
    exit_lane = _new_exit_lane(db_session, sede)
    tariffs = _add_standard_tariffs(db_session, sede)
    entry_at = datetime(2026, 3, 10, 5, 50, tzinfo=LOCAL_ZONE)
    entry = _entry(client, headers, entry_lane, "ABC123", entry_at)
    assert entry.status_code == 201
    assert entry.json()["dia_operativo"] == "2026-03-09"
    assert entry.json()["franja"] == "NOCTURNA"
    cobro = db_session.get(Cobro, UUID(entry.json()["cobro_id"]))
    assert cobro is not None
    prepare_paid_pass(cobro, entry_at)

    exit_result = ValidarSalidaVehiculoUseCase(
        db_session,
        clock=FixedClock(datetime(2026, 3, 10, 9, 0, tzinfo=LOCAL_ZONE)),
    ).ejecutar("ABC123", exit_lane.id)
    next_day_charge = (
        db_session.query(Cobro)
        .filter(
            Cobro.placa == "ABC123",
            Cobro.sede_id == sede.id,
            Cobro.dia_operativo == date(2026, 3, 10),
        )
        .one_or_none()
    )

    assert next_day_charge is not None
    assert next_day_charge.tarifa_id == tariffs["day"].id
    assert next_day_charge.estado == "PENDIENTE"
    assert exit_result["barrera_abre"] is False


def test_scenario_8_monday_pass_does_not_prevent_tuesday_daytime_charge(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
    prepare_paid_pass: Callable[[Cobro, datetime], Pase],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "Escenario8")
    tariffs = _add_standard_tariffs(db_session, sede)
    monday_entry_at = datetime(2026, 3, 9, 19, 0, tzinfo=LOCAL_ZONE)
    monday_entry = _entry(client, headers, entry_lane, "ABC123", monday_entry_at)
    assert monday_entry.status_code == 201
    assert monday_entry.json()["dia_operativo"] == "2026-03-09"
    assert monday_entry.json()["franja"] == "NOCTURNA"
    monday_charge = db_session.get(Cobro, UUID(monday_entry.json()["cobro_id"]))
    assert monday_charge is not None
    prepare_paid_pass(monday_charge, monday_entry_at)

    tuesday_entry = _entry(
        client,
        headers,
        entry_lane,
        "ABC123",
        datetime(2026, 3, 10, 7, 0, tzinfo=LOCAL_ZONE),
    )

    assert tuesday_entry.status_code == 201
    assert tuesday_entry.json()["pase_vigente"] is False
    assert tuesday_entry.json()["dia_operativo"] == "2026-03-10"
    assert tuesday_entry.json()["franja"] == "DIURNA"
    assert tuesday_entry.json()["cobro_creado"] is True
    assert tuesday_entry.json()["tarifa_id"] == str(tariffs["day"].id)
    assert (
        db_session.query(Cobro)
        .filter(Cobro.placa == "ABC123", Cobro.sede_id == sede.id)
        .count()
        == 2
    )


def test_scenario_9_manual_plate_entry_is_persisted(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "Escenario9")
    _add_standard_tariffs(db_session, sede)
    event_id = uuid4()
    entry = _entry(
        client,
        headers,
        entry_lane,
        "ABC123",
        datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE),
        event_id,
        confidence=0.0,
        manual=True,
    )

    assert entry.status_code == 201
    assert db_session.get(EventoAcceso, event_id).lectura_manual is True
    assert entry.json()["cobro_creado"] is True


def test_low_confidence_automatic_read_requires_operator_validation(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "UmbralHU12")
    _add_standard_tariffs(db_session, sede)
    confidence = settings.lpr_confidence_threshold / 2

    response = _entry(
        client,
        headers,
        entry_lane,
        "XYZ789",
        datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE),
        confidence=confidence,
    )

    assert response.status_code == 422


def test_confirming_same_payment_twice_is_idempotent_through_use_case(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "PagoIdempotente")
    _add_standard_tariffs(db_session, sede)
    entry_at = datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE)
    entry = _entry(client, headers, entry_lane, "ABC123", entry_at)
    assert entry.status_code == 201
    cobro_id = UUID(entry.json()["cobro_id"])
    referencia = f"hu11-{uuid4()}"
    use_case = RegistrarPagoEfectivoUseCase(
        db_session,
        clock=FixedClock(entry_at),
    )
    first = use_case.ejecutar(cobro_id, referencia)
    repeated = use_case.ejecutar(cobro_id, referencia)

    assert first.pago_id == repeated.pago_id
    assert first.pase_id == repeated.pase_id
    assert first.repetido is False
    assert repeated.repetido is True
    assert db_session.get(Cobro, cobro_id).valor == first.valor_pagado
    assert (
        db_session.query(Pago)
        .filter(Pago.cobro_id == cobro_id)
        .count()
        == 1
    )
    assert (
        db_session.query(Pase)
        .filter(Pase.cobro_id == cobro_id)
        .count()
        == 1
    )

def test_cupo_por_tipo_estado_lleno_y_liberacion_al_salir(
    db_session: Session,
    operator_client: tuple[TestClient, dict[str, str]],
    prepare_paid_pass: Callable[[Cobro, datetime], Pase],
) -> None:
    client, headers = operator_client
    sede, entry_lane = _new_sede(db_session, "CuposHU13")
    exit_lane = _new_exit_lane(db_session, sede)
    sede.cupos_carro = 1
    sede.cupos_moto = 1
    db_session.flush()
    _add_standard_tariffs(db_session, sede)

    t1 = datetime(2026, 3, 10, 8, 0, tzinfo=LOCAL_ZONE)
    t2 = datetime(2026, 3, 10, 8, 5, tzinfo=LOCAL_ZONE)
    t3 = datetime(2026, 3, 10, 8, 10, tzinfo=LOCAL_ZONE)

    # 1. Primer carro entra ok (cupo carro queda 1/1 -> LLENO)
    r_carro_1 = _entry(client, headers, entry_lane, "ABC123", t1)
    assert r_carro_1.status_code == 201
    cobro_1 = db_session.get(Cobro, UUID(r_carro_1.json()["cobro_id"]))
    assert cobro_1 is not None
    prepare_paid_pass(cobro_1, t1)

    # 2. Segundo carro es rechazado con LLENO (409) y no crea cobro extra
    r_carro_2 = _entry(client, headers, entry_lane, "DEF456", t2)
    assert r_carro_2.status_code == 409
    assert "LLENO" in r_carro_2.json()["detail"]
    assert db_session.query(Cobro).filter(Cobro.sede_id == sede.id).count() == 1

    # 3. Moto sigue entrando porque tiene su propio cupo independiente
    r_moto = _entry(client, headers, entry_lane, "ABC12D", t3)
    assert r_moto.status_code == 201

    # 4. Sale el primer carro pagado -> abre barrera, libera cupo y entra otro
    salida = ValidarSalidaVehiculoUseCase(
        db_session,
        clock=FixedClock(datetime(2026, 3, 10, 9, 0, tzinfo=LOCAL_ZONE)),
    ).ejecutar("ABC123", exit_lane.id)
    assert salida["barrera_abre"] is True

    r_carro_3 = _entry(
        client,
        headers,
        entry_lane,
        "GHI789",
        datetime(2026, 3, 10, 9, 5, tzinfo=LOCAL_ZONE),
    )
    assert r_carro_3.status_code == 201