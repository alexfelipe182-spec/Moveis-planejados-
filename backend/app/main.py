from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": settings.app_name}


@app.get("/", tags=["system"])
def root():
    return {"message": "API de Moveis Planejados funcionando"}
