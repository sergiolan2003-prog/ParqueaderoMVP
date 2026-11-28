# Sistema de Parqueadero MVP

MVP de un sistema de parqueadero con reconocimiento de placas (LPR). Incluye
API para accesos, autenticación, administración de tarifas y generación inicial
de cobros; el frontend muestra el estado de la API.

## Stack

- Python 3.12, FastAPI, pydantic-settings, SQLAlchemy y Alembic
- PostgreSQL 16
- React y Vite
- pytest, httpx, Ruff, Vitest, React Testing Library y ESLint
- Docker Compose

## Estructura

```text
backend/
  app/
    core/                 # Configuración validada y conexión a base de datos
    modules/              # accesos, cobros, pagos, tarifas y auth
      <modulo>/
        domain/
        application/
        infrastructure/
        api/
  alembic/                # Migraciones de base de datos
  tests/
    unit/
    scenarios/
frontend/                 # Aplicación React/Vite y pruebas Vitest
docs/                     # Documentación complementaria
docker-compose.yml        # API, PostgreSQL y frontend
```

## Requisitos

- Docker Desktop con Docker Compose v2
- Node.js 24 o compatible para ejecutar pruebas del frontend localmente
- Python 3.12 para ejecutar pruebas y Ruff localmente

## Ejecución con Docker Compose

Clona el repositorio y crea el archivo local de variables:

```powershell
git clone https://github.com/sergiolan2003-prog/ParqueaderoMVP.git
cd ParqueaderoMVP
Copy-Item .env.example .env
docker compose up --build
```

La API aplica las migraciones de Alembic al arrancar. Servicios disponibles:

- Frontend: http://localhost:5173
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- PostgreSQL: `localhost:5433` (host) / `db:5432` (Docker network)

Para detener los servicios, pulsa `Ctrl+C` y ejecuta `docker compose down`.
El volumen de PostgreSQL persiste entre reinicios; `docker compose down -v`
lo elimina junto con sus datos.

## Base de datos y migraciones

El esquema PostgreSQL se administra con Alembic. Al iniciar la API, Compose
aplica automáticamente las migraciones pendientes. Para aplicarlas manualmente
o consultar la revisión activa:

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
docker compose exec api alembic history
```

Para crear una revisión, ejecuta el comando desde el contenedor y completa la
migración revisando explícitamente las operaciones y restricciones:

```powershell
docker compose exec api alembic revision -m "descripcion del cambio"
```

Para revertir la revisión más reciente:

```powershell
docker compose exec api alembic downgrade -1
```

El SQL completo puede generarse sin conectarse a PostgreSQL. Desde la raíz del
repositorio, en Windows PowerShell 5.1, usa `cmd.exe` para que la redirección
guarde el flujo UTF-8 del contenedor sin la conversión a UTF-16 de PowerShell:

```powershell
cmd.exe /c "docker compose run --rm --no-deps -T api alembic upgrade head --sql > docs\schema.sql"
```

Las pruebas de integración usan PostgreSQL real en una base separada cuyo
nombre termina en `_test`; no reutilizan la base de desarrollo. Reconstruye la
imagen de API después de cambiar el backend y antes de ejecutar pytest, porque
el código se copia a la imagen durante el build:

```powershell
docker compose build api
docker compose run --rm api pytest -v
docker compose run --rm api ruff check .
```

El detalle de las tablas, las restricciones y las decisiones del modelo está
en [docs/modelo-de-datos.md](docs/modelo-de-datos.md).

## Pruebas y calidad

Backend en Docker:

```powershell
docker compose run --rm api pytest
docker compose run --rm api ruff check .
```

### HU-10: escenarios y reglas críticas

Con Docker Desktop activo y `.env` configurado, ejecuta desde la raíz:

```powershell
docker compose build api
docker compose run --rm api pytest -v
docker compose run --rm api ruff check .
```

La suite de integración usa PostgreSQL y mantiene como `xfail` estricto los
flujos pendientes de HU-12 y la generación automática de cobro de S-05.

Backend local, desde `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pytest
ruff check .
```

Frontend, desde `frontend/`:

```powershell
npm ci
npm test
npm run lint
npm run build
```

La prueba de salud valida `GET /health` y la respuesta `{"status": "ok"}`.
Las pruebas Vitest cubren el cliente HTTP, el login, la autorización por rol,
las vistas administrativas y la visualización del estado de la API. El frontend
guarda el JWT en `sessionStorage` para conservar la sesión al recargar la pestaña;
al cerrar sesión se elimina. La API actual no ofrece revocación de JWT, por lo
que un token copiado seguiría vigente hasta su expiración.

Para validar la comunicación real a través de los proxies, abre Docker Desktop
y verifica que los puertos 5432, 8000 y 5173 estén libres. Este comando usa un
proyecto y volumen PostgreSQL separados de los de desarrollo:

```powershell
docker compose -p par28-integration up --build -d
```

Con el frontend disponible en `http://localhost:5173`, define credenciales de
un operador de prueba como variables de entorno en la sesión y ejecuta:

```powershell
$env:INTEGRATION_OPERATOR_USERNAME = "<usuario operador>"
# Define INTEGRATION_OPERATOR_PASSWORD mediante el mecanismo seguro de tu entorno.
npm.cmd run test:integration
```

Al terminar, detén únicamente ese proyecto:

```powershell
docker compose -p par28-integration down
```

La prueba verifica `/health`, login, usuario autenticado, autorización por rol,
la ruta de tarifas sin barra final y la validación real de las rutas existentes
de entrada, pago y salida. El login y `/auth/me` leen el usuario de PostgreSQL;
las solicitudes de negocio se detienen en validación. No crea ni actualiza
datos de negocio. No imprime el token ni los valores de credenciales. Para
ejecutarla contra otro origen del frontend, define `FRONTEND_BASE_URL`.
También consulta `http://localhost:8000/openapi.json` y compara métodos, rutas,
campos requeridos y esquemas de respuesta con el contrato observado por los
servicios del frontend; para otro origen de FastAPI, define `API_BASE_URL`.

En ejecución local de Vite, `VITE_API_BASE_URL` queda vacío para usar rutas
relativas y `API_PROXY_TARGET` apunta al backend, por defecto
`http://localhost:8000`. En Docker Compose, el frontend se sirve por Nginx y
este reenvía las rutas API al servicio `api:8000`; dentro del contenedor no se
usa `localhost` para localizar el backend. Si se configura `VITE_API_BASE_URL`
con un origen distinto, ese servidor debe permitir CORS para el frontend.

## Variables de entorno

Copia `.env.example` a `.env` antes de iniciar Compose. El archivo de ejemplo
documenta todas las variables requeridas:

| Variable | Uso |
| --- | --- |
| `APP_NAME` | Nombre mostrado por la API y Swagger |
| `APP_ENV` | Entorno de ejecución |
| `DATABASE_URL` | URL de SQLAlchemy para la API |
| `OPERATING_DAY_START` | Hora local de inicio del día operativo |
| `DAYTIME_START` / `DAYTIME_END` | Inicio y fin exclusivo de la franja diurna |
| `NIGHTTIME_START` / `NIGHTTIME_END` | Inicio y fin exclusivo de la franja nocturna |
| `OPERATING_TIMEZONE` | Zona horaria usada para calcular día y franja |
| `LPR_CONFIDENCE_THRESHOLD` | Umbral de confianza LPR entre 0 y 1, aplicado en HU-06 |
| `POSTGRES_DB` | Base inicializada por PostgreSQL |
| `POSTGRES_USER` | Usuario inicializado por PostgreSQL |
| `POSTGRES_PASSWORD` | Contraseña local de ejemplo para PostgreSQL |
| `JWT_SECRET` | Clave obligatoria para firmar tokens; mínimo 32 caracteres |
| `JWT_ALGORITHM` | Algoritmo JWT, por defecto `HS256` |
| `JWT_EXPIRE_MINUTES` | Duración del token en minutos, por defecto `60` |
| `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` | Credenciales iniciales del administrador |
| `SEED_OPERADOR_USERNAME` / `SEED_OPERADOR_PASSWORD` | Credenciales iniciales del operador |
| `VITE_API_BASE_URL` | URL base del cliente frontend; vacía usa el proxy del mismo origen |
| `API_PROXY_TARGET` | Destino de FastAPI para el proxy de Vite en desarrollo local |

Compose valida las variables obligatorias y nombra la variable faltante. La
configuración de la API también valida sus valores requeridos al iniciar.
`POSTGRES_PASSWORD` en `.env.example` es solo para desarrollo local; usa
valores seguros y fuera del repositorio para otros entornos. No subas `.env`.

## Autenticación y usuarios de prueba

HU-09 agrega la tabla `usuario` al modelo de datos. Esta decisión incorpora
identidades, roles y contraseñas autenticadas sin mezclar autenticación con
los módulos de cobros, accesos o tarifas. Las contraseñas se almacenan únicamente
como hashes Argon2. El inicio de sesión usa Swagger OAuth2 con el botón
`Authorize` y las rutas protegidas aceptan el token Bearer.

Usuarios de prueba documentados desde las variables de entorno:

| Rol | Usuario | Contraseña |
| --- | --- | --- |
| Administrador | `admin_prueba` | `AdminPrueba123!` |
| Operador | `operador_prueba` | `OperadorPrueba123!` |

El seed es idempotente y se ejecuta después de las migraciones al iniciar el
contenedor `api`.

Las rutas de salida (`POST /accesos/salida`) requieren el rol `OPERADOR` y las
de administración (`POST /tarifas/`) requieren `ADMINISTRADOR`. La salida
rechaza vehículos no registrados y consulta la deuda pendiente del día
operativo y sede asociados al carril.

### Administración y consultas (HU-16 / PAR-17)

Las rutas administrativas requieren un JWT con rol `ADMINISTRADOR`:

- `GET /tarifas/` lista las versiones históricas y vigentes; acepta filtros
  opcionales `sede_id`, `tipo_vehiculo` (`CARRO` o `MOTO`) y `franja`
  (`DIURNA` o `NOCTURNA`). `POST /tarifas/` crea una tarifa o una nueva versión.
  RN-02 exige que la tarifa diurna sea estrictamente mayor que la nocturna;
  RN-07 cierra la vigencia anterior al día previo al inicio de la nueva.
- `GET /sedes/` lista sedes para selección. `GET /sedes/{sede_id}/cupos`
  consulta sus cupos y `PUT` en la misma ruta actualiza `cupos_carro` y
  `cupos_moto`; ambos valores deben ser mayores o iguales a cero.
- `GET /consultas/eventos` filtra eventos por `placa`, `desde` y `hasta`.
  `GET /consultas/cobros` acepta esos filtros y `estado` (`PENDIENTE`,
  `PAGADO`, `ANULADO` o `VENCIDO`). Las placas se normalizan a mayúsculas;
  ambas consultas aceptan `page` (desde 1) y `page_size` (de 1 a 100), y
  devuelven `items`, `total`, `page`, `page_size` y `total_pages`.
- `GET /configuracion/operativa` consulta los horarios diurno/nocturno y el
  umbral LPR. `PUT` en la misma ruta actualiza los valores de forma persistente;
  las franjas deben cubrir las 24 horas sin huecos ni solapamientos, y el umbral
  debe estar entre 0 y 1. Antes del primer cambio administrativo se conservan
  los valores configurados en el entorno.

Las fechas de eventos se interpretan en la zona horaria configurada para la
operación; las fechas de cobros corresponden a `dia_operativo`. Un rango donde
`desde` sea posterior a `hasta` se rechaza con HTTP 422.

La interfaz web en `http://localhost:5173` solicita login y muestra las pestañas
Tarifas, Cupos y Consultas únicamente a `ADMINISTRADOR`. Un `OPERADOR` recibe
un mensaje de acceso denegado. La pestaña Tarifas permite crear una tarifa o
iniciar una nueva versión desde la tarifa vigente; Cupos permite actualizar
los valores por sede; Consultas pagina eventos y cobros con sus filtros;
Configuración modifica horarios y umbral LPR, que se aplican en los siguientes
ingresos sin reiniciar la API.

## Ingreso de vehículos (HU-06)

Las rutas de ingreso requieren el rol `OPERADOR` y registran el evento de
acceso junto con el flujo de cobro de HU-19:

- `POST /accesos/entrada` conserva el contrato existente: recibe `evento_id`,
  `placa`, `carril_id` y `ocurrido_en`. `confianza_lpr` sigue siendo opcional
  (por defecto `1.0`).
- `POST /accesos/entrada/simulada` usa el lector simulado. Requiere `carril_id`;
  `evento_id`, `ocurrido_en`, `placa` y `confianza_lpr` son opcionales. Si no
  se especifica la placa o la confianza, el simulador las genera.

Ambas rutas responden con el mismo esquema. Una confianza menor que
`LPR_CONFIDENCE_THRESHOLD` se rechaza con HTTP 422, salvo que
`lectura_manual` sea `true` en la ruta compatible `/entrada`. El ingreso manual
completo sigue fuera del alcance de HU-06 (HU-12). Reutilizar un `evento_id`
registrado devuelve HTTP 409. Los esquemas y ejemplos están disponibles en
Swagger: http://localhost:8000/docs.

La cadena de validación aplica confianza, cupo y estado del pase en ese orden.
El validador de cupo es no bloqueante hasta que se implemente HU-13. Consulta
[docs/patron-chain-of-responsibility.md](docs/patron-chain-of-responsibility.md)
para extenderla.

### Ingreso por imagen (HU-27)

`POST /accesos/entrada/imagen` recibe multipart/form-data con los campos
`imagen` y `carril_id`. También acepta `placa_simulada` y
`confianza_simulada`; ambos tienen prioridad sobre los datos inferidos del
nombre del archivo.
El panel obtiene los carriles persistidos mediante `GET /accesos/carriles` y
separa el carril de entrada del de salida.

El archivo simulado usa el nombre `PLACA_CONFIANZA.ext`, por ejemplo
`ABC123_0.92.jpg`. La placa y la confianza pueden controlarse por los campos
opcionales. Los nombres inválidos, las placas inválidas, los archivos que no
son imágenes y los archivos mayores a `LPR_IMAGE_MAX_BYTES` se rechazan.

Las variables `LPR_READER_TYPE`, `LPR_IMAGE_STORAGE_PATH` y
`LPR_IMAGE_MAX_BYTES` configuran el adaptador, el volumen local y el límite.
La ruta guardada se registra en `evento_acceso.foto_url`.

### HU-11: pago efectivo y pase vigente

El operador registra pagos idempotentes en `POST /pagos/efectivo`. El contrato,
las reglas del State del cobro y la vigencia del pase se documentan en
[docs/pagos-hu-11.md](docs/pagos-hu-11.md).

## Flujo Git y commits

- `main` contiene versiones liberadas; `develop` integra cambios.
- Crea cada historia desde `develop` en una rama
  `feature/<id-historia>-<descripción>`.
- Abre el pull request hacia `develop`; no hagas commits directos a las ramas
  base ni mezcles un PR antes de su revisión.
- Usa Conventional Commits en español, con el identificador de historia y un
  verbo en imperativo. Tipos permitidos: `feat`, `fix`, `chore`, `docs`,
  `test`, `refactor`, `build` y `ci`.

Ejemplo: `feat(HU-01): configura backend FastAPI`.
