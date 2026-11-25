# HU-11: pago en efectivo y pase

## Endpoint

`POST /pagos/efectivo` requiere el rol `OPERADOR`.

Solicitud:

```json
{
  "cobro_id": "UUID del cobro pendiente",
  "referencia_pago": "referencia-unica"
}
```

El cliente no envía el valor: el pago toma exactamente `cobro.valor`. La
respuesta incluye identificadores del pago, cobro y pase; referencia, valor,
método, estado, día operativo y marcas de tiempo. El primer registro responde
`201`; una repetición idempotente devuelve el mismo cuerpo con `200`.

Respuestas de error documentadas en Swagger:

- `404`: cobro inexistente.
- `409`: cobro ya pagado con otra referencia, anulado/vencido, o referencia
  utilizada para otro cobro.
- `422`: solicitud inválida, incluyendo un intento de enviar un importe.

## Transacción e idempotencia

El caso de uso bloquea el cobro con `SELECT FOR UPDATE`, comprueba primero la
referencia y el estado, y crea pago, transición y pase dentro de un savepoint.
La operación confirma la transacción solo después de persistir los tres datos.
Las restricciones PostgreSQL `uq_pago_referencia`, `uq_pago_cobro_id` y
`uq_pase_cobro_id` respaldan la idempotencia y limitan cada cobro a un pago y
un pase. El repositorio distingue las violaciones de dichas restricciones;
otros errores de integridad no se convierten en conflictos de idempotencia.

## State del cobro

Los estados de dominio están en `backend/app/modules/cobros/domain/states.py`:

- `CobroPendiente`: permite `confirmar_pago()` y produce `CobroPagado`; no
  autoriza la salida.
- `CobroPagado`: rechaza una transición de pago nueva y solo autoriza la salida
  si el pase asociado sigue vigente.
- `CobroAnulado` y `CobroVencido`: rechazan pagos y no autorizan la salida.

La API delega la transición al caso de uso; no implementa reglas de estado.

## Vigencia del pase

El pase tiene un `cobro_id` único y conserva el día operativo en que se pagó.
El vencimiento se calcula con el servicio `OperatingDayService`, la hora de
inicio y la zona de la sede. Su intervalo es `[pagado_en, inicio del siguiente
día operativo)`, usando `America/Bogota`; por ejemplo, un pago el lunes a las
10:00 vence el martes a las 06:00. El día operativo se deriva del reloj
inyectado de HU-03. Las filas de pase anteriores a HU-11 conservan sus datos y
pueden tener `cobro_id` y `dia_operativo` nulos.

## Diagrama State

El equipo debe dibujar su propio diagrama. Clases y relaciones reales:

- `EstadoCobro`: comportamiento común para transición a pagado y autorización
  de salida.
- `CobroPendiente`: único estado que permite transicionar a `CobroPagado`.
- `CobroPagado`: autoriza la salida únicamente con pase vigente.
- `CobroAnulado` y `CobroVencido`: no admiten pago ni autorizan la salida.
- `estado_cobro(codigo)`: crea el objeto concreto a partir del estado persistido
  en `Cobro.estado`.
- `RegistrarPagoEfectivoUseCase`: consulta el estado y delega la transición.
- `ValidarSalidaVehiculoUseCase`: delega al estado la decisión de autorizar.

El pago y el pase se relacionan al cobro; el pase conserva la vigencia y el día
operativo de ese pago.

## Pruebas y evidencia pendiente

Con Docker Desktop y `.env` local configurado, desde la raíz:

```powershell
docker compose config --quiet
docker compose build api
docker compose run --rm api pytest -v
docker compose run --rm api ruff check .
docker compose up --build -d
```

La captura de Swagger debe adjuntarse al PR tras la verificación visual. No se
incluye aquí un diagrama generado: el diagrama State queda pendiente de elaborar
por el grupo.
