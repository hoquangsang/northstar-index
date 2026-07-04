from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import HealthResponse, StatsResponse
from app.services.stats_service import get_stats

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.app_env)


@router.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    return get_stats()
