from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, time
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import FixedClock, SystemClock, get_clock
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.modules.accesos.infrastructure.models import Carril, Sede, Vehiculo
from app.modules.auth.infrastructure.models import Usuario
from app.modules.auth.infrastructure.seed import seed_users
from app.modules.auth.infrastructure.tokens import PyJwtTokenService
from app.modules.cobros.infrastructure.models import Cobro
from app.modules.pagos.api.v1.router import router as pagos_router
from app.modules.pagos.application.services import RegistrarPagoEfectivoUseCase
from app.modules.pagos.infrastructure.models import Pago
from app.modules.pases.infrastructure.models import Pase
from app.modules.tarifas.infrastructure.models import Tarifa

LOCAL_ZONE = ZoneInfo("America/Bogota")


@pytest.fixture
def cashier_client(
    db_session: Session,
) -> Iterator[tuple[TestClient, dict[str, str], Callable[[datetime], None]]]:
    seed_users(db_session)
    clock = {"value": FixedClock(datetime(2026, 3, 10, 10, tzinfo=LOCAL_ZONE))}

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def set_time(instant: datetime) -> None:
        clock["value"] = FixedClock(instant)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_clock] = lambda: clock["value"]
    try:
        with TestClient(app) as client:
            login = client.post(
                "/auth/login",
                data={
                    "username": settings.seed_operador_username,
                    "password": settings.seed_operador_password,
                },
            )
            assert login.status_code == 200
            yield (
                client,
                {"Authorization": f"Bearer {login.json()['access_token']}"},
                set_time,
            )
    finally:
        app.dependency_overrides.pop(get_clock, None)
        app.dependency_overrides.pop(get_db, None)


def _new_charge(
    session: Session,
    *,
    plate: str = "ABC123",
    operating_day: date = date(2026, 3, 10),
    state: str = "PENDIENTE",
) -> tuple[Sede, Cobro, Carril, Carril]:
    sede = Sede(
        nombre=f"Pago-{uuid4()}",
        zona_horaria="America/Bogota",
        inicio_dia_operativo=time(6),
        cupos_carro=20,
        cupos_moto=10,
    )
    session.add(sede)
    session.flush()
    entry_lane = Carril(sede_id=sede.id, sentido="ENTRADA")
    exit_lane = Carril(sede_id=sede.id, sentido="SALIDA")
    vehicle = Vehiculo(placa=plate, tipo="CARRO")
    session.add_all([entry_lane, exit_lane, vehicle])
    session.flush()
    tariff = Tarifa(
        sede_id=sede.id,
        tipo_vehiculo="CARRO",
        franja="DIURNA",
        valor=Decimal("12000.00"),
        vigente_desde=date(2026, 1, 1),
    )
    session.add(tariff)
    session.flush()
    charge = Cobro(
        placa=plate,
        sede_id=sede.id,
        dia_operativo=operating_day,
        tarifa_id=tariff.id,
        valor=tariff.valor,
        estado=state,
    )
    session.add(charge)
    session.flush()
    return sede, charge, entry_lane, exit_lane


def test_cash_payment_updates_charge_creates_pass_and_authorizes_exit(
    db_session: Session,
    cashier_client: tuple[TestClient, dict[str, str], Callable[[datetime], None]],
) -> None:
    client, headers, set_time = cashier_client
    _, cobro, _, exit_lane = _new_charge(db_session)
    paid_at = datetime(2026, 3, 10, 10, 0, tzinfo=LOCAL_ZONE)

    response = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={
            "cobro_id": str(cobro.id),
            "referencia_pago": f"cash-{uuid4()}",
        },
    )

    assert response.status_code == 201
    result = response.json()
    payment = db_session.get(Pago, UUID(result["pago_id"]))
    charge = db_session.get(Cobro, cobro.id)
    pass_record = db_session.get(Pase, UUID(result["pase_id"]))
    assert payment is not None
    assert charge is not None
    assert pass_record is not None
    assert payment.cobro_id == cobro.id
    assert payment.medio == "EFECTIVO"
    assert payment.valor == cobro.valor == Decimal("12000.00")
    assert charge.estado == "PAGADO"
    assert pass_record.cobro_id == cobro.id
    assert pass_record.dia_operativo == date(2026, 3, 10)
    assert result["dia_operativo"] == "2026-03-10"
    assert result["estado_cobro"] == "PAGADO"
    assert result["metodo_pago"] == "EFECTIVO"
    assert datetime.fromisoformat(result["pagado_en"]) == paid_at.astimezone(UTC)
    assert datetime.fromisoformat(result["vence_pase_en"]) == datetime(
        2026, 3, 11, 11, 0, tzinfo=ZoneInfo("UTC")
    )

    set_time(datetime(2026, 3, 10, 12, 0, tzinfo=LOCAL_ZONE))
    exit_response = client.post(
        "/accesos/salida",
        headers=headers,
        json={"placa": cobro.placa, "carril_id": str(exit_lane.id)},
    )
    assert exit_response.status_code == 200
    assert exit_response.json()["barrera_abre"] is True


def test_same_reference_returns_original_payment_and_pass(
    db_session: Session,
    cashier_client: tuple[TestClient, dict[str, str], Callable[[datetime], None]],
) -> None:
    client, headers, _ = cashier_client
    _, cobro, _, _ = _new_charge(db_session)
    payload = {
        "cobro_id": str(cobro.id),
        "referencia_pago": f"same-{uuid4()}",
    }

    first = client.post("/pagos/efectivo", headers=headers, json=payload)
    repeated = client.post("/pagos/efectivo", headers=headers, json=payload)

    assert first.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    assert (
        db_session.query(func.count(Pago.id))
        .filter(Pago.cobro_id == cobro.id)
        .scalar()
        == 1
    )
    assert (
        db_session.query(func.count(Pase.id))
        .filter(Pase.cobro_id == cobro.id)
        .scalar()
        == 1
    )
    assert db_session.get(Cobro, cobro.id).valor == Decimal("12000.00")


def test_payment_rejects_missing_paid_cancelled_and_reused_references(
    db_session: Session,
    cashier_client: tuple[TestClient, dict[str, str], Callable[[datetime], None]],
) -> None:
    client, headers, _ = cashier_client
    _, paid_charge, _, _ = _new_charge(db_session)
    _, other_charge, _, _ = _new_charge(
        db_session,
        plate="DEF456",
    )
    _, cancelled_charge, _, _ = _new_charge(
        db_session,
        plate="GHI789",
        state="ANULADO",
    )
    reference = f"conflict-{uuid4()}"
    paid = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={
            "cobro_id": str(paid_charge.id),
            "referencia_pago": reference,
        },
    )
    assert paid.status_code == 201

    already_paid = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={
            "cobro_id": str(paid_charge.id),
            "referencia_pago": f"different-{uuid4()}",
        },
    )
    cancelled = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={
            "cobro_id": str(cancelled_charge.id),
            "referencia_pago": f"cancelled-{uuid4()}",
        },
    )
    reused_reference = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={"cobro_id": str(other_charge.id), "referencia_pago": reference},
    )
    missing = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={"cobro_id": str(uuid4()), "referencia_pago": f"missing-{uuid4()}"},
    )

    assert already_paid.status_code == 409
    assert "otra referencia" in already_paid.json()["detail"]
    assert cancelled.status_code == 409
    assert "ANULADO" in cancelled.json()["detail"]
    assert reused_reference.status_code == 409
    assert "otro cobro" in reused_reference.json()["detail"]
    assert missing.status_code == 404
    assert db_session.get(Cobro, other_charge.id).estado == "PENDIENTE"
    assert db_session.get(Cobro, cancelled_charge.id).estado == "ANULADO"
    charge_ids = (paid_charge.id, other_charge.id, cancelled_charge.id)
    assert (
        db_session.query(Pago).filter(Pago.cobro_id.in_(charge_ids)).count() == 1
    )
    assert (
        db_session.query(Pase).filter(Pase.cobro_id.in_(charge_ids)).count() == 1
    )


@pytest.mark.parametrize("state", ["ANULADO", "VENCIDO"])
def test_nonpayable_charge_states_do_not_create_payment_or_pass(
    db_session: Session,
    cashier_client: tuple[TestClient, dict[str, str], Callable[[datetime], None]],
    state: str,
) -> None:
    client, headers, _ = cashier_client
    _, charge, _, _ = _new_charge(db_session, state=state)

    response = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={
            "cobro_id": str(charge.id),
            "referencia_pago": f"nonpayable-{uuid4()}",
        },
    )

    assert response.status_code == 409
    assert state in response.json()["detail"]
    assert db_session.get(Cobro, charge.id).estado == state
    assert db_session.query(Pago).filter(Pago.cobro_id == charge.id).count() == 0
    assert db_session.query(Pase).filter(Pase.cobro_id == charge.id).count() == 0


def test_payment_does_not_accept_client_supplied_amount(
    db_session: Session,
    cashier_client: tuple[TestClient, dict[str, str], Callable[[datetime], None]],
) -> None:
    client, headers, _ = cashier_client
    _, cobro, _, _ = _new_charge(db_session)

    unauthenticated = client.post(
        "/pagos/efectivo",
        json={
            "cobro_id": str(cobro.id),
            "referencia_pago": f"unauth-{uuid4()}",
        },
    )
    response = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={
            "cobro_id": str(cobro.id),
            "referencia_pago": f"no-amount-{uuid4()}",
            "valor_pagado": "1.00",
        },
    )

    assert unauthenticated.status_code == 401
    assert response.status_code == 422
    assert db_session.get(Cobro, cobro.id).estado == "PENDIENTE"
    assert db_session.query(Pago).filter(Pago.cobro_id == cobro.id).count() == 0
    assert db_session.query(Pase).filter(Pase.cobro_id == cobro.id).count() == 0


def test_payment_and_pass_roll_back_together_on_pass_persistence_error(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, cobro, _, _ = _new_charge(db_session)

    def fail_to_save_pass(self, pase) -> None:
        raise RuntimeError("Falló la persistencia del pase.")

    monkeypatch.setattr(
        "app.modules.pagos.application.services.SqlAlchemyPaseRepository.add",
        fail_to_save_pass,
    )
    with pytest.raises(RuntimeError, match="persistencia del pase"):
        RegistrarPagoEfectivoUseCase(
            db_session,
            FixedClock(datetime(2026, 3, 10, 10, tzinfo=LOCAL_ZONE)),
        ).ejecutar(cobro.id, f"rollback-{uuid4()}")

    db_session.refresh(cobro)
    assert cobro.estado == "PENDIENTE"
    assert db_session.query(Pago).filter(Pago.cobro_id == cobro.id).count() == 0
    assert db_session.query(Pase).filter(Pase.cobro_id == cobro.id).count() == 0


def test_payment_at_0550_pass_expires_exclusively_at_0600(
    db_session: Session,
    cashier_client: tuple[TestClient, dict[str, str], Callable[[datetime], None]],
) -> None:
    client, headers, set_time = cashier_client
    _, cobro, entry_lane, exit_lane = _new_charge(
        db_session,
        operating_day=date(2026, 3, 9),
    )
    paid_at = datetime(2026, 3, 10, 5, 50, tzinfo=LOCAL_ZONE)
    set_time(paid_at)
    payment = client.post(
        "/pagos/efectivo",
        headers=headers,
        json={
            "cobro_id": str(cobro.id),
            "referencia_pago": f"early-{uuid4()}",
        },
    )
    assert payment.status_code == 201
    assert payment.json()["dia_operativo"] == "2026-03-09"
    assert payment.json()["vence_pase_en"] == "2026-03-10T11:00:00Z"

    entry_before_expiry = client.post(
        "/accesos/entrada",
        headers=headers,
        json={
            "evento_id": str(uuid4()),
            "placa": cobro.placa,
            "carril_id": str(entry_lane.id),
            "ocurrido_en": datetime(
                2026, 3, 10, 5, 59, tzinfo=LOCAL_ZONE
            ).isoformat(),
        },
    )
    assert entry_before_expiry.status_code == 201
    assert entry_before_expiry.json()["pase_vigente"] is True
    assert entry_before_expiry.json()["cobro_creado"] is False

    set_time(datetime(2026, 3, 10, 6, 0, tzinfo=LOCAL_ZONE))
    expired_exit = client.post(
        "/accesos/salida",
        headers=headers,
        json={"placa": cobro.placa, "carril_id": str(exit_lane.id)},
    )
    assert expired_exit.status_code == 200
    assert expired_exit.json()["barrera_abre"] is False

    entry_after_expiry = client.post(
        "/accesos/entrada",
        headers=headers,
        json={
            "evento_id": str(uuid4()),
            "placa": cobro.placa,
            "carril_id": str(entry_lane.id),
            "ocurrido_en": datetime(2026, 3, 10, 6, 0, tzinfo=LOCAL_ZONE).isoformat(),
        },
    )
    assert entry_after_expiry.status_code == 201
    assert entry_after_expiry.json()["pase_vigente"] is False
    assert entry_after_expiry.json()["cobro_creado"] is True


def test_concurrent_cash_payments_create_one_payment_and_pass(
    database_engine,
) -> None:
    sessions = sessionmaker(bind=database_engine)
    plate_suffix = uuid4().int % 1_000_000
    plate = f"XYZ{plate_suffix:03d}"[-6:]
    sede_id = uuid4()
    cobro_id = uuid4()
    tarifa_id = uuid4()
    payment_at = datetime(2026, 3, 10, 10, 0, tzinfo=LOCAL_ZONE)
    reference = f"concurrent-{uuid4()}"
    username = f"operador-{uuid4()}"

    with sessions.begin() as session:
        session.add(
            Sede(
                id=sede_id,
                nombre=f"Concurrencia-{uuid4()}",
                zona_horaria="America/Bogota",
                inicio_dia_operativo=time(6),
                cupos_carro=10,
                cupos_moto=5,
            )
        )
        session.add(Vehiculo(placa=plate, tipo="CARRO"))
        session.add(
            Tarifa(
                id=tarifa_id,
                sede_id=sede_id,
                tipo_vehiculo="CARRO",
                franja="DIURNA",
                valor=Decimal("9000.00"),
                vigente_desde=date(2026, 1, 1),
            )
        )
        session.flush()
        session.add(
            Usuario(
                id=uuid4(),
                username=username,
                password_hash="hash-no-usado-en-la-prueba",
                rol="OPERADOR",
                activo=True,
            )
        )
        session.add(
            Cobro(
                id=cobro_id,
                placa=plate,
                sede_id=sede_id,
                dia_operativo=date(2026, 3, 10),
                tarifa_id=tarifa_id,
                valor=Decimal("9000.00"),
                estado="PENDIENTE",
            )
        )
    token = PyJwtTokenService(SystemClock()).emitir(username, "OPERADOR")

    barrier = Barrier(2)

    def pay() -> tuple[int, dict]:
        test_app = FastAPI()
        test_app.include_router(pagos_router)

        def override_get_db() -> Iterator[Session]:
            with sessions() as session:
                yield session

        test_app.dependency_overrides[get_db] = override_get_db
        test_app.dependency_overrides[get_clock] = lambda: FixedClock(payment_at)
        with TestClient(test_app) as client:
            barrier.wait(timeout=10)
            response = client.post(
                "/pagos/efectivo",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "cobro_id": str(cobro_id),
                    "referencia_pago": reference,
                },
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: pay(), range(2)))

    with sessions() as session:
        payment_count = (
            session.query(func.count(Pago.id))
            .filter(Pago.cobro_id == cobro_id)
            .scalar()
        )
        pass_count = (
            session.query(func.count(Pase.id))
            .filter(Pase.cobro_id == cobro_id)
            .scalar()
        )

    assert sorted(result[0] for result in results) == [200, 201]
    assert results[0][1] == results[1][1]
    assert payment_count == pass_count == 1
