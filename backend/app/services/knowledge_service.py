from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from typing import Any

from app.config.settings import get_settings
from app.agents.ai_brain import get_chroma_client, get_embedding_model
from app.utils.exceptions import (
    ChromaDBException,
    EmbeddingException,
    FileTooLargeException,
    InvalidFileTypeException,
)
from app.utils.logger import get_logger
from app.models.database import Filter, FilterOperator, get_admin_db

settings = get_settings()
logger = get_logger(__name__)

ALLOWED_FILE_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


async def upload_knowledge_base(
    user_id: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> dict[str, Any]:
    """
    Uploads and trains a knowledge base document.
    Steps: validate → extract text → chunk → embed → store ChromaDB → save DB
    """
    if content_type not in ALLOWED_FILE_TYPES:
        raise InvalidFileTypeException(
            f"File type {content_type} not supported",
            file_type=content_type,
            allowed_types=list(ALLOWED_FILE_TYPES.values()),
            user_id=user_id,
            operation="upload_kb",
        )

    file_size = len(file_bytes)
    if file_size > settings.max_upload_size_bytes:
        raise FileTooLargeException(
            f"File too large: {file_size / 1024 / 1024:.1f}MB",
            file_size_mb=round(file_size / 1024 / 1024, 2),
            max_size_mb=settings.max_upload_size_mb,
            user_id=user_id,
            operation="upload_kb",
        )

    file_type = ALLOWED_FILE_TYPES[content_type]
    db = get_admin_db()

    kb_record = await db.insert(
        "knowledge_base",
        {
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "training_status": "processing",
            "trained": False,
            "chunk_count": 0,
        },
    )
    kb_id = kb_record["id"]

    logger.info(
        "kb_upload_started",
        user_id=user_id,
        filename=filename,
        file_type=file_type,
    )

    try:
        text = await asyncio.to_thread(_extract_text, file_bytes, file_type)
        if not text.strip():
            raise EmbeddingException(
                "No text extracted from file",
                user_id=user_id,
                operation="extract_text",
            )

        chunks = _chunk_text(
            text,
            chunk_size=settings.embedding_chunk_size,
            overlap=settings.embedding_chunk_overlap,
        )

        await asyncio.to_thread(_embed_and_store, user_id, chunks, kb_id)

        await db.update(
            "knowledge_base",
            kb_id,
            {
                "content": text[:10000],
                "training_status": "trained",
                "trained": True,
                "chunk_count": len(chunks),
            },
        )

        logger.info("kb_training_completed", user_id=user_id, kb_id=kb_id, chunk_count=len(chunks))
        return {**kb_record, "chunk_count": len(chunks), "training_status": "trained"}

    except (EmbeddingException, ChromaDBException) as e:
        await db.update("knowledge_base", kb_id, {
            "training_status": "failed",
            "training_error": str(e),
        })
        logger.error("kb_training_failed", user_id=user_id, kb_id=kb_id, error=str(e))
        raise

    except Exception as e:
        await db.update("knowledge_base", kb_id, {
            "training_status": "failed",
            "training_error": str(e)[:500],
        })
        logger.error("kb_training_unexpected_error", user_id=user_id, error=str(e))
        raise EmbeddingException(
            f"Training failed: {e}",
            user_id=user_id,
            operation="upload_kb",
        ) from e


async def auto_update_knowledge_base(
    user_id: str,
    approved_faqs: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Auto-updates knowledge base from approved FAQ entries.

    Called after owner reviews and approves AI-generated FAQ entries.
    Appends new Q&A pairs to existing KB content and retrains.

    Args:
        user_id: Business owner's user_id
        approved_faqs: List of {"question": str, "answer": str} dicts

    Returns:
        Updated KB record dict with new chunk count
    """
    if not approved_faqs:
        return {"message": "No FAQs to add", "chunks_added": 0}

    db = get_admin_db()

    # Format new FAQ entries as clean text
    new_content = "\n\n".join([
        f"Q: {faq['question']}\nA: {faq['answer']}"
        for faq in approved_faqs
    ])

    logger.info(
        "kb_auto_update_started",
        user_id=user_id,
        faq_count=len(approved_faqs),
    )

    # Find existing auto-update KB record or create new one
    existing_records = await db.list_records(
        "knowledge_base",
        filters=[
            Filter("user_id", FilterOperator.EQ, user_id),
            Filter("filename", FilterOperator.EQ, "auto_generated_faq.txt"),
        ],
        page_size=1,
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    if existing_records:
        # Append to existing auto-generated KB
        kb_record = existing_records[0]
        kb_id = kb_record["id"]
        existing_content = kb_record.get("content", "")
        updated_content = existing_content + "\n\n" + new_content

        await db.update("knowledge_base", kb_id, {
            "training_status": "processing",
            "trained": False,
            "updated_at": now_iso,
        })
    else:
        # Create new auto-generated KB record
        kb_record = await db.insert("knowledge_base", {
            "user_id": user_id,
            "filename": "auto_generated_faq.txt",
            "file_type": "txt",
            "file_size": len(new_content.encode()),
            "training_status": "processing",
            "trained": False,
            "chunk_count": 0,
        })
        kb_id = kb_record["id"]
        updated_content = new_content

    try:
        # Chunk new content only (don't re-embed everything)
        new_chunks = _chunk_text(
            new_content,
            chunk_size=settings.embedding_chunk_size,
            overlap=settings.embedding_chunk_overlap,
        )

        # Add new chunks to existing ChromaDB collection
        await asyncio.to_thread(
            _embed_and_store,
            user_id,
            new_chunks,
            f"{kb_id}_autoupdate_{int(datetime.now().timestamp())}",
        )

        # Update KB record with combined content
        await db.update("knowledge_base", kb_id, {
            "content": updated_content[:10000],
            "training_status": "trained",
            "trained": True,
            "chunk_count": (kb_record.get("chunk_count") or 0) + len(new_chunks),
            "updated_at": now_iso,
        })

        logger.info(
            "kb_auto_update_completed",
            user_id=user_id,
            new_chunks=len(new_chunks),
        )

        return {
            "kb_id": kb_id,
            "chunks_added": len(new_chunks),
            "faqs_added": len(approved_faqs),
            "message": f"Added {len(approved_faqs)} FAQ entries successfully",
        }

    except Exception as e:
        await db.update("knowledge_base", kb_id, {
            "training_status": "failed",
            "training_error": str(e)[:500],
        })
        logger.error("kb_auto_update_failed", user_id=user_id, error=str(e))
        raise EmbeddingException(
            f"Auto-update failed: {e}",
            user_id=user_id,
            operation="auto_update_kb",
        ) from e


async def generate_faq_gaps(user_id: str) -> list[dict[str, str]]:
    """
    Analyses today's escalated/low-confidence conversations
    and uses Groq LLM to generate FAQ entries for the gaps.

    Returns list of {"question": str, "answer": str, "source_count": int}
    Owner reviews these before they're added to KB.
    """
    from groq import Groq
    import json

    db = get_admin_db()
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    # Fetch today's escalated conversations
    escalated_convs = await db.list_records(
        "conversations",
        filters=[
            Filter("user_id", FilterOperator.EQ, user_id),
            Filter("escalated", FilterOperator.EQ, True),
            Filter("created_at", FilterOperator.GTE, today),
        ],
        page_size=50,
    )

    if not escalated_convs:
        logger.info("kb_gap_analysis_no_escalations", user_id=user_id)
        return []

    # Fetch inbound messages for each escalated conversation
    unanswered_questions: list[str] = []
    for conv in escalated_convs[:20]:  # Cap at 20 to stay within context
        messages = await db.list_records(
            "messages",
            filters=[
                Filter("conversation_id", FilterOperator.EQ, conv["id"]),
                Filter("direction", FilterOperator.EQ, "inbound"),
            ],
            page_size=3,
            order_by="created_at",
            ascending=True,
        )
        for msg in messages:
            content = msg.get("content", "").strip()
            if content and len(content) > 10:
                unanswered_questions.append(content)

    if not unanswered_questions:
        return []

    # Deduplicate
    unique_questions = list(dict.fromkeys(unanswered_questions))[:15]

    # Fetch business profile for context
    profile = await db.get_by_field("business_profiles", "user_id", user_id)
    business_name = profile.get("business_name", "this business") if profile else "this business"
    industry = profile.get("industry", "general") if profile else "general"
    description = profile.get("description", "") if profile else ""

    logger.info(
        "kb_gap_analysis_started",
        user_id=user_id,
        question_count=len(unique_questions),
    )

    # Call Groq to generate FAQ entries
    client = Groq(api_key=settings.groq_api_key)

    questions_text = "\n".join([f"- {q}" for q in unique_questions])

    prompt = f"""You are a knowledge base assistant for {business_name}, a {industry} business.
{f'Business description: {description}' if description else ''}

The following are customer questions that the AI bot could NOT answer today.
Generate clear, helpful FAQ entries for each unique question.

UNANSWERED QUESTIONS:
{questions_text}

Rules:
1. Only generate FAQ entries for questions that are reasonable for this business
2. If a question is too specific or personal, skip it
3. Keep answers concise and factual
4. Group similar questions into one FAQ entry
5. Generate at most 8 FAQ entries

Respond with ONLY a valid JSON array, no other text:
[
  {{
    "question": "clear question text",
    "answer": "helpful answer text",
    "source_count": 1
  }}
]"""

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content or "[]"
        # Strip any markdown code blocks if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        faqs = json.loads(raw)

        if not isinstance(faqs, list):
            return []

        # Validate structure
        validated = [
            {
                "question": str(f.get("question", "")).strip(),
                "answer": str(f.get("answer", "")).strip(),
                "source_count": int(f.get("source_count", 1)),
            }
            for f in faqs
            if f.get("question") and f.get("answer")
        ]

        logger.info(
            "kb_gap_analysis_completed",
            user_id=user_id,
            faqs_generated=len(validated),
        )

        return validated

    except Exception as e:
        logger.error("kb_gap_analysis_llm_failed", user_id=user_id, error=str(e))
        return []


async def delete_knowledge_base(user_id: str, kb_id: str) -> None:
    """Deletes a KB document from Supabase and ChromaDB."""
    db = get_admin_db()
    record = await db.get_by_id("knowledge_base", kb_id)

    try:
        def _delete_from_chroma() -> None:
            chroma = get_chroma_client()
            collection_name = f"{settings.chroma_collection_name}_{user_id}"
            try:
                collection = chroma.get_collection(collection_name)
                chunk_count = record.get("chunk_count", 0)
                ids = [f"{kb_id}_{i}" for i in range(chunk_count)]
                if ids:
                    collection.delete(ids=ids)
            except Exception:
                pass

        await asyncio.to_thread(_delete_from_chroma)
    except Exception as e:
        logger.warning("kb_chromadb_delete_failed", kb_id=kb_id, error=str(e))

    await db.delete("knowledge_base", kb_id)
    logger.info("kb_deleted", user_id=user_id, kb_id=kb_id)


def _extract_text(file_bytes: bytes, file_type: str) -> str:
    if file_type == "txt":
        return file_bytes.decode("utf-8", errors="ignore")
    elif file_type == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise EmbeddingException(f"PDF extraction failed: {e}", operation="extract_text") from e
    elif file_type == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise EmbeddingException(f"DOCX extraction failed: {e}", operation="extract_text") from e
    return ""


def _chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def _embed_and_store(user_id: str, chunks: list[str], kb_id: str) -> None:
    try:
        model = get_embedding_model()
        embeddings = model.encode(chunks).tolist()

        chroma = get_chroma_client()
        collection_name = f"{settings.chroma_collection_name}_{user_id}"

        collection = chroma.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [f"{kb_id}_{i}" for i in range(len(chunks))]
        collection.add(ids=ids, documents=chunks, embeddings=embeddings)

        logger.info(
            "chromadb_chunks_stored",
            user_id=user_id,
            collection=collection_name,
            chunk_count=len(chunks),
        )
    except Exception as e:
        raise ChromaDBException(
            f"ChromaDB store failed: {e}",
            user_id=user_id,
            operation="embed_and_store",
        ) from e