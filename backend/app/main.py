from fastapi import FastAPI
from app.core.config import settings
from app.modules.accesos.api.v1.router import router as accesos_router

app = FastAPI(title=settings.app_name)

# Registrar rutas del módulo de accesos
app.include_router(accesos_router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}