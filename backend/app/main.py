from fastapi import FastAPI

from app.core.config import settings
from app.modules.accesos.api.v1.router import router as accesos_router
from app.modules.auth.api.router import router as auth_router
from app.modules.cobros.api.v1.router import router as cobros_router
from app.modules.pagos.api.v1.router import router as pagos_router
from app.modules.tarifas.api.v1.router import router as tarifas_router

app = FastAPI(title=settings.app_name)

# Registrar rutas de los módulos
app.include_router(accesos_router)
app.include_router(tarifas_router)
app.include_router(auth_router)
app.include_router(pagos_router)
app.include_router(cobros_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
