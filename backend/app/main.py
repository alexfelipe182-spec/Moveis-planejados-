from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.routes import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": settings.app_name}


@app.get("/", tags=["system"])
def root():
    return {"message": "API de Moveis Planejados funcionando"}
