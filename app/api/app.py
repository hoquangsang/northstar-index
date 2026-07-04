from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import chat, health, sync
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(sync.router)
    return app
