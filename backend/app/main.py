from fastapi import FastAPI

from app.core.config import settings
from app.modules.accesos.api.v1.carriles import router as carriles_router
from app.modules.accesos.api.v1.router import router as accesos_router
from app.modules.auth.api.router import router as auth_router
from app.modules.cobros.api.v1.router import router as cobros_router
from app.modules.configuracion.api.router import router as configuracion_router
from app.modules.consultas.api.v1.router import router as consultas_router
from app.modules.pagos.api.v1.router import router as pagos_router
from app.modules.sedes.api.v1.router import router as sedes_router
from app.modules.tarifas.api.v1.router import router as tarifas_router

app = FastAPI(title=settings.app_name)

# Registrar rutas de los módulos
app.include_router(accesos_router)
app.include_router(carriles_router)
app.include_router(tarifas_router)
app.include_router(auth_router)
app.include_router(pagos_router)
app.include_router(cobros_router)
app.include_router(sedes_router)
app.include_router(consultas_router)
app.include_router(configuracion_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
