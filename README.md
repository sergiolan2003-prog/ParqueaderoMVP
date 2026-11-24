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
- PostgreSQL: `localhost:5432`

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
El frontend tiene una prueba Vitest que verifica la consulta y visualización
del estado de la API.

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
