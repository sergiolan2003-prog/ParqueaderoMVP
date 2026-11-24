# Modelo de datos

El esquema se crea con las revisiones Alembic `0002_modelo_datos`,
`0003_usuario_auth` y `0004_pases`, posteriores a `0001_initial`. Las nueve
tablas representan las entidades del modelo del parqueadero. Las claves UUID se generan con
`uuid4` desde Python y `gen_random_uuid()` en PostgreSQL, excepto
`evento_acceso.id`: el gateway debe proporcionarlo para que funcione como
identificador idempotente. Los importes usan `NUMERIC(12,2)` y los instantes
usan `TIMESTAMPTZ`.

## Tablas y restricciones

| Tabla | Columnas y tipos | Restricciones adicionales |
| --- | --- | --- |
| `sede` | `id` UUID, `nombre`/`zona_horaria` string, `inicio_dia_operativo` TIME, `cupos_carro`/`cupos_moto` INTEGER | `nombre` es único; ambos cupos deben ser mayores o iguales a cero. |
| `carril` | `id`/`sede_id` UUID, `sentido` string | `sede_id` referencia `sede`; `sentido` es `ENTRADA` o `SALIDA`. |
| `vehiculo` | `placa`/`tipo` string | `placa` es PK y debe ser igual a `upper(placa)`; `tipo` es `CARRO` o `MOTO`. |
| `usuario` | `id` UUID, `username`/`password_hash`/`rol` string, `activo` BOOLEAN | `username` es único; rol `OPERADOR` o `ADMINISTRADOR`; `activo` tiene valor inicial `true`. |
| `evento_acceso` | `id` UUID, `placa`/`foto_url` string, `carril_id` UUID, `ocurrido_en` TIMESTAMPTZ, `confianza_lpr` FLOAT, `lectura_manual` BOOLEAN | `placa` referencia `vehiculo`; `carril_id` referencia `carril`; la confianza está entre 0 y 1; `lectura_manual` es `NOT NULL` y tiene valor inicial `false`; `foto_url` admite `NULL`. |
| `tarifa` | `id`/`sede_id` UUID, `tipo_vehiculo`/`franja` string, `valor` NUMERIC(12,2), `vigente_desde`/`vigente_hasta` DATE | `sede_id` referencia `sede`; tipo `CARRO`/`MOTO`; franja `DIURNA`/`NOCTURNA`; valor no negativo; vigencia final nula o no anterior a la inicial; único por sede, tipo, franja e inicio de vigencia. |
| `cobro` | `id`/`sede_id`/`tarifa_id` UUID, `placa`/`estado` string, `dia_operativo` DATE, `valor` NUMERIC(12,2) | Referencias a `vehiculo`, `sede` y `tarifa`; `tarifa_id` es obligatorio; valor no negativo; estado `PENDIENTE`/`PAGADO`/`ANULADO`/`VENCIDO`; único por `(placa, sede_id, dia_operativo)` como `uq_cobro_placa_sede_dia`. |
| `pago` | `id`/`cobro_id` UUID, `medio`/`referencia_pasarela` string, `valor` NUMERIC(12,2), `pagado_en` TIMESTAMPTZ | `cobro_id` referencia `cobro`; medio `EFECTIVO`/`TARJETA`/`PSE`/`NEQUI`; valor positivo; `referencia_pasarela` obligatoria y única como `uq_pago_referencia`. |
| `pase` | `id`/`sede_id` UUID, `placa` string, `vigente_desde`/`vigente_hasta` TIMESTAMPTZ | Referencias a `vehiculo` y `sede`; el fin de vigencia no puede anteceder al inicio; índice para consultar pases vigentes por placa y sede. |

Las claves foráneas y las restricciones CHECK restantes se nombran mediante la
convención de metadatos definida en `app.core.database`; los nombres explícitos
de unicidad se mantienen tal como se especifican arriba. Las relaciones son
`sede` 1-N `carril`, `sede` 1-N `tarifa`, `carril` 1-N `evento_acceso`,
`vehiculo` 1-N `evento_acceso`, `vehiculo` 1-N `cobro`, `tarifa` 1-N `cobro`,
`cobro` 1-N `pago`, `vehiculo` 1-N `pase` y `sede` 1-N `pase`.

## Decisiones

- `pago.referencia_pasarela` es `NOT NULL`: PostgreSQL permite múltiples valores
  `NULL` en una restricción `UNIQUE`. Un identificador obligatorio también
  permite idempotencia para pagos en efectivo; el componente que los registra
  genera una referencia única.
- La placa se valida en mayúsculas en la base de datos. Así, `abc123` no puede
  coexistir con `ABC123` ni eludir la clave primaria mediante diferencias de
  mayúsculas.
- Cada cobro conserva `tarifa_id` y el valor aplicado. La relación mantiene
  identificada la tarifa asociada al cobro cuando se consultan tarifas con
  vigencias diferentes.
- `pase` registra un intervalo absoluto de vigencia. El flujo de entrada lo
  considera activo cuando el instante del evento cae dentro del intervalo y
  corresponde a la misma placa y sede.
- `uq_cobro_placa_sede_dia` respalda la idempotencia por día operativo. El
  repositorio inserta con `ON CONFLICT DO NOTHING`; un conflicto conserva el
  evento de acceso sin duplicar el cobro.
- `evento_acceso.id` no tiene default en el servidor: el gateway que recibe el
  evento proporciona su UUID de idempotencia.
- Los campos de configuración no reciben valores por defecto en la base de
  datos; la excepción explícita es `evento_acceso.lectura_manual`.
- No se insertan sedes, tarifas ni otros datos de referencia o ejemplo.

La migración `0004_pases` agrega la vigencia de pases. El ingreso se expone
directamente en `POST /accesos/entrada`; el backend resuelve día operativo y
franja mediante `OperatingDayService`, y usa el motor de tarifas para todos
los tipos de vehículo. Una tarifa configurada en `0.00` no genera cobro.

El endpoint está disponible en el backend directo (`http://localhost:8000`,
Swagger en `http://localhost:8000/docs`). Nginx actualmente solo reenvía
`/health`; conectar las demás rutas al frontend queda fuera de este alcance.
