from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import SyncRequest, SyncResponse
from app.services.sync_service import run_ingestion_sync

router = APIRouter()


@router.post("/sync", response_model=SyncResponse)
def sync(request: SyncRequest) -> SyncResponse:
    try:
        return run_ingestion_sync(
            limit=request.limit,
            dry_run=request.dry_run,
            local_only=request.local_only,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
