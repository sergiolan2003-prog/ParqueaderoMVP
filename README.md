# Sistema de Parqueadero MVP

Esqueleto inicial de un sistema de parqueadero con reconocimiento de placas
(LPR). Esta HU prepara la estructura, la API, la interfaz y el entorno de
desarrollo; no implementa lógica de negocio.

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
| `POSTGRES_DB` | Base inicializada por PostgreSQL |
| `POSTGRES_USER` | Usuario inicializado por PostgreSQL |
| `POSTGRES_PASSWORD` | Contraseña local de ejemplo para PostgreSQL |

Compose valida las variables obligatorias y nombra la variable faltante. La
configuración de la API también valida sus valores requeridos al iniciar.
`POSTGRES_PASSWORD` en `.env.example` es solo para desarrollo local; usa
valores seguros y fuera del repositorio para otros entornos. No subas `.env`.

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
