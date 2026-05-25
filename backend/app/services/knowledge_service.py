from __future__ import annotations

import asyncio
import io
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.config.settings import get_settings
from app.utils.exceptions import (
    ChromaDBException,
    EmbeddingException,
    FileTooLargeException,
    InvalidFileTypeException,
)
from app.utils.logger import get_logger, log_latency
from app.models.database import get_admin_db

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

    Steps:
    1. Validate file type and size
    2. Extract text from file
    3. Chunk text (256-512 tokens, 50 overlap)
    4. Embed chunks via sentence-transformers
    5. Store in ChromaDB (user-specific collection)
    6. Save metadata to Supabase

    Returns KB record dict.
    """
    # Validate file type
    if content_type not in ALLOWED_FILE_TYPES:
        raise InvalidFileTypeException(
            f"File type {content_type} not supported",
            file_type=content_type,
            allowed_types=list(ALLOWED_FILE_TYPES.values()),
            user_id=user_id,
            operation="upload_kb",
        )

    # Validate file size
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

    # Save initial record with pending status
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
        file_size_kb=file_size // 1024,
    )

    try:
        # Extract text from file
        text = await asyncio.to_thread(
            _extract_text, file_bytes, file_type
        )

        if not text.strip():
            raise EmbeddingException(
                "No text extracted from file",
                user_id=user_id,
                operation="extract_text",
            )

        # Chunk text
        chunks = _chunk_text(
            text,
            chunk_size=settings.embedding_chunk_size,
            overlap=settings.embedding_chunk_overlap,
        )

        logger.info(
            "kb_text_extracted",
            user_id=user_id,
            chunk_count=len(chunks),
        )

        # Embed and store in ChromaDB
        await asyncio.to_thread(
            _embed_and_store,
            user_id=user_id,
            chunks=chunks,
            kb_id=kb_id,
        )

        # Update KB record as trained
        await db.update(
            "knowledge_base",
            kb_id,
            {
                "content": text[:10000],  # Store first 10k chars only
                "training_status": "trained",
                "trained": True,
                "chunk_count": len(chunks),
            },
        )

        logger.info(
            "kb_training_completed",
            user_id=user_id,
            kb_id=kb_id,
            chunk_count=len(chunks),
        )

        return {**kb_record, "chunk_count": len(chunks), "training_status": "trained"}

    except (EmbeddingException, ChromaDBException) as e:
        await db.update(
            "knowledge_base",
            kb_id,
            {
                "training_status": "failed",
                "training_error": str(e),
            },
        )
        logger.error(
            "kb_training_failed",
            user_id=user_id,
            kb_id=kb_id,
            error=str(e),
        )
        raise

    except Exception as e:
        await db.update(
            "knowledge_base",
            kb_id,
            {
                "training_status": "failed",
                "training_error": str(e)[:500],
            },
        )
        logger.error(
            "kb_training_unexpected_error",
            user_id=user_id,
            kb_id=kb_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise EmbeddingException(
            f"Training failed: {e}",
            user_id=user_id,
            operation="upload_kb",
        ) from e


def _extract_text(file_bytes: bytes, file_type: str) -> str:
    """Extracts plain text from PDF, TXT, or DOCX."""
    if file_type == "txt":
        return file_bytes.decode("utf-8", errors="ignore")

    elif file_type == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as e:
            raise EmbeddingException(
                f"PDF extraction failed: {e}",
                operation="extract_text",
            ) from e

    elif file_type == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise EmbeddingException(
                f"DOCX extraction failed: {e}",
                operation="extract_text",
            ) from e

    return ""


def _chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[str]:
    """
    Chunks text into overlapping segments.
    Sweet spot: 256-512 tokens with 50-token overlap.
    Word-boundary aware — never splits mid-word.
    """
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


def _embed_and_store(
    user_id: str,
    chunks: list[str],
    kb_id: str,
) -> None:
    """
    Embeds chunks and stores in user-specific ChromaDB collection.
    Sync function — called via asyncio.to_thread.

    Each user gets their own collection:
    collection name = f"knowledge_base_{user_id}"
    This ensures data isolation at the vector store level.
    """
    try:
        model = SentenceTransformer(settings.embedding_model)
        embeddings = model.encode(chunks).tolist()

        chroma = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        collection_name = f"{settings.chroma_collection_name}_{user_id}"

        # Get or create user collection
        try:
            collection = chroma.get_collection(collection_name)
        except Exception:
            collection = chroma.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        # Store with unique IDs
        ids = [f"{kb_id}_{i}" for i in range(len(chunks))]
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
        )

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


async def delete_knowledge_base(
    user_id: str,
    kb_id: str,
) -> None:
    """Deletes a KB document from Supabase and ChromaDB."""
    db = get_admin_db()
    record = await db.get_by_id("knowledge_base", kb_id)

    # Remove from ChromaDB
    try:
        def _delete_from_chroma() -> None:
            chroma = chromadb.PersistentClient(
                path=settings.chroma_persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            collection_name = (
                f"{settings.chroma_collection_name}_{user_id}"
            )
            try:
                collection = chroma.get_collection(collection_name)
                # Delete all chunks for this kb_id
                chunk_count = record.get("chunk_count", 0)
                ids = [f"{kb_id}_{i}" for i in range(chunk_count)]
                if ids:
                    collection.delete(ids=ids)
            except Exception:
                pass  # Collection may not exist

        await asyncio.to_thread(_delete_from_chroma)
    except Exception as e:
        logger.warning(
            "kb_chromadb_delete_failed",
            kb_id=kb_id,
            error=str(e),
        )

    # Delete from Supabase
    await db.delete("knowledge_base", kb_id)

    logger.info("kb_deleted", user_id=user_id, kb_id=kb_id)