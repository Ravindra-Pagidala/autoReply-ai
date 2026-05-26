from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.utils.exceptions import (
    EmbeddingException,
    FileTooLargeException,
    InvalidFileTypeException,
)
from app.utils.logger import get_logger
from app.models.database import Filter, FilterOperator, get_admin_db
from app.schemas.base import KnowledgeBaseResponse, SuccessResponse
from app.services.knowledge_service import (
    delete_knowledge_base,
    upload_knowledge_base,
    generate_faq_gaps,
    auto_update_knowledge_base,
)
from app.api.auth import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class ApprovedFAQ(BaseModel):
    question: str
    answer: str
    source_count: int = 1


class AutoUpdateRequest(BaseModel):
    approved_faqs: list[ApprovedFAQ]


@router.post("/upload", response_model=KnowledgeBaseResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    """Upload and train a KB document. Supported: PDF, TXT, DOCX."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_bytes = await file.read()

    try:
        record = await upload_knowledge_base(
            user_id=user["id"],
            filename=file.filename,
            content_type=file.content_type or "text/plain",
            file_bytes=file_bytes,
        )
        return KnowledgeBaseResponse(**record)
    except FileTooLargeException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InvalidFileTypeException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except EmbeddingException as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/list", response_model=list[KnowledgeBaseResponse])
async def list_documents(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[KnowledgeBaseResponse]:
    """Lists all KB documents for current user."""
    db = get_admin_db()
    rows = await db.list_records(
        "knowledge_base",
        filters=[Filter("user_id", FilterOperator.EQ, user["id"])],
        page_size=50,
        select="id,user_id,filename,file_type,file_size,chunk_count,training_status,training_error,trained,created_at,updated_at",
    )
    return [KnowledgeBaseResponse(**r) for r in rows]


@router.delete("/{kb_id}", response_model=SuccessResponse)
async def delete_document(
    kb_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Deletes a KB document from Supabase and ChromaDB."""
    try:
        await delete_knowledge_base(user_id=user["id"], kb_id=kb_id)
        return SuccessResponse(message="Document deleted")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/gaps", response_model=list[dict])
async def get_knowledge_gaps(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Analyses today's escalated conversations and generates FAQ suggestions.
    Returns list of suggested FAQ entries for owner review.
    Does NOT save anything yet — owner must approve via POST /knowledge/auto-update.
    """
    try:
        faqs = await generate_faq_gaps(user_id=user["id"])
        return faqs
    except Exception as e:
        logger.error("kb_gaps_endpoint_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/auto-update", response_model=SuccessResponse)
async def auto_update_kb(
    body: AutoUpdateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """
    Applies approved FAQ entries to the knowledge base.
    Appends to existing auto_generated_faq.txt and retrains.
    Only call after owner has reviewed /knowledge/gaps output.
    """
    if not body.approved_faqs:
        raise HTTPException(status_code=400, detail="No FAQs provided")

    try:
        result = await auto_update_knowledge_base(
            user_id=user["id"],
            approved_faqs=[f.model_dump() for f in body.approved_faqs],
        )
        return SuccessResponse(
            message=f"Added {result['faqs_added']} FAQ entries. "
                    f"AI will now answer these questions correctly."
        )
    except EmbeddingException as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e