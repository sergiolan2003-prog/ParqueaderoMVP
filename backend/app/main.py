from fastapi import FastAPI
from app.core.config import settings
from app.modules.accesos.api.v1.router import router as accesos_router
from app.modules.tarifas.api.v1.router import router as tarifas_router

app = FastAPI(title=settings.app_name)

# Registrar rutas de los módulos
app.include_router(accesos_router)
app.include_router(tarifas_router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}