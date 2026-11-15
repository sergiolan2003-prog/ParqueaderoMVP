# Modelo de datos

El esquema de la HU-02 se crea con la revisión Alembic
`0002_modelo_datos`, posterior a `0001_initial`. Las siete tablas representan
las entidades del modelo del parqueadero. Las claves UUID se generan con
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
| `evento_acceso` | `id` UUID, `placa`/`foto_url` string, `carril_id` UUID, `ocurrido_en` TIMESTAMPTZ, `confianza_lpr` FLOAT, `lectura_manual` BOOLEAN | `placa` referencia `vehiculo`; `carril_id` referencia `carril`; la confianza está entre 0 y 1; `lectura_manual` es `NOT NULL` y tiene valor inicial `false`; `foto_url` admite `NULL`. |
| `tarifa` | `id`/`sede_id` UUID, `tipo_vehiculo`/`franja` string, `valor` NUMERIC(12,2), `vigente_desde`/`vigente_hasta` DATE | `sede_id` referencia `sede`; tipo `CARRO`/`MOTO`; franja `DIURNA`/`NOCTURNA`; valor no negativo; vigencia final nula o no anterior a la inicial; único por sede, tipo, franja e inicio de vigencia. |
| `cobro` | `id`/`sede_id`/`tarifa_id` UUID, `placa`/`estado` string, `dia_operativo` DATE, `valor` NUMERIC(12,2) | Referencias a `vehiculo`, `sede` y `tarifa`; `tarifa_id` es obligatorio; valor no negativo; estado `PENDIENTE`/`PAGADO`/`ANULADO`/`VENCIDO`; único por `(placa, sede_id, dia_operativo)` como `uq_cobro_placa_sede_dia`. |
| `pago` | `id`/`cobro_id` UUID, `medio`/`referencia_pasarela` string, `valor` NUMERIC(12,2), `pagado_en` TIMESTAMPTZ | `cobro_id` referencia `cobro`; medio `EFECTIVO`/`TARJETA`/`PSE`/`NEQUI`; valor positivo; `referencia_pasarela` obligatoria y única como `uq_pago_referencia`. |

Las claves foráneas y las restricciones CHECK restantes se nombran mediante la
convención de metadatos definida en `app.core.database`; los nombres explícitos
de unicidad se mantienen tal como se especifican arriba. Las relaciones son
`sede` 1-N `carril`, `sede` 1-N `tarifa`, `carril` 1-N `evento_acceso`,
`vehiculo` 1-N `evento_acceso`, `vehiculo` 1-N `cobro`, `tarifa` 1-N `cobro`
y `cobro` 1-N `pago`.

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
- `evento_acceso.id` no tiene default en el servidor: el gateway que recibe el
  evento proporciona su UUID de idempotencia.
- Los campos de configuración no reciben valores por defecto en la base de
  datos; la excepción explícita es `evento_acceso.lectura_manual`.
- No se insertan sedes, tarifas ni otros datos de referencia o ejemplo.

## Alcance pendiente

Este esquema no implementa reglas de negocio, cálculo del día operativo,
validación RN-02 sobre la relación de precios diurna/nocturna, endpoints,
frontend ni datos de ejemplo. Agregar un tipo de vehículo, una franja o un
medio de pago requiere una migración que amplíe el CHECK correspondiente; no
requiere cambiar el motor de cobro.
