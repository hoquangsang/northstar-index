from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.errors import GeminiQueryError, KnowledgeBaseNotReadyError
from app.schemas import AskRequest, AskResponse
from app.services.chat_service import answer_question

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        return answer_question(request.question, request.language)
    except KnowledgeBaseNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except GeminiQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
