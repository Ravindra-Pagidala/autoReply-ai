from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.settings import get_settings
from app.utils.circuit_breaker import groq_circuit, CircuitOpenException
from app.utils.exceptions import (
    ChromaDBException,
    EmbeddingException,
    EscalationRequiredException,
    KnowledgeBaseEmptyException,
    LLMMalformedOutputException,
    LLMRateLimitException,
    LLMTimeoutException,
    LLMException,
    RAGException,
)
from app.utils.logger import get_logger, log_retry_attempt
from app.models.database import Filter, FilterOperator, get_admin_db
from app.schemas.ai import AgentState, AIResponse, ChannelType, IntentType
from app.schemas.base import (
    ConversationCreate,
    ConversationUpdate,
    EscalationCreate,
    LeadCreate,
    MessageCreate,
    NotificationCreate,
)
from app.prompts.ai_brain_prompt import (
    build_after_hours_suffix,
    build_clarify_prompt,
    build_escalation_message,
    build_system_prompt,
    sanitize_customer_input,
)

settings = get_settings()
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Singletons — initialised once at module load
# ─────────────────────────────────────────────────────────────────────────

def _init_embedding_model() -> SentenceTransformer:
    """Load embedding model once at startup."""
    logger.info(
        "embedding_model_loading",
        model=settings.embedding_model,
    )
    model = SentenceTransformer(settings.embedding_model)
    logger.info("embedding_model_loaded")
    return model


def _init_chroma_client() -> chromadb.PersistentClient:
    """Initialise ChromaDB persistent client."""
    logger.info(
        "chromadb_client_init",
        path=settings.chroma_persist_directory,
    )
    client = chromadb.PersistentClient(
        path=settings.chroma_persist_directory,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    logger.info("chromadb_client_ready")
    return client


# Module-level singletons
_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = _init_embedding_model()
    return _embedding_model


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = _init_chroma_client()
    return _chroma_client


def _build_groq_client() -> ChatGroq:
    """Build Groq LLM client with timeout and temperature."""
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=settings.groq_temperature,
        max_tokens=settings.groq_max_tokens,
        timeout=settings.groq_timeout_seconds,
        max_retries=0,  # We handle retries ourselves via tenacity
    )


# ─────────────────────────────────────────────────────────────────────────
# Working hours check
# ─────────────────────────────────────────────────────────────────────────

def _is_within_working_hours(
    working_hours_start: str | None,
    working_hours_end: str | None,
    timezone_str: str = "Asia/Kolkata",
) -> bool:
    """
    Checks if current time is within business working hours.
    Returns True if within hours or if hours not configured.
    """
    if not working_hours_start or not working_hours_end:
        return True

    try:
        import pytz
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        current_time = now.strftime("%H:%M")
        return working_hours_start <= current_time <= working_hours_end
    except Exception:
        # If timezone check fails, assume within hours
        logger.warning(
            "working_hours_check_failed",
            timezone=timezone_str,
        )
        return True


# ─────────────────────────────────────────────────────────────────────────
# RAG Retrieval Node
# ─────────────────────────────────────────────────────────────────────────

async def retriever_node(state: AgentState) -> AgentState:
    """
    LangGraph Node 1: RAG Retrieval.

    Retrieves top-k relevant chunks from ChromaDB
    BEFORE the LLM is called.
    Graceful degradation if KB empty or ChromaDB fails.

    Updates state:
      → rag_context
      → rag_chunks_found
      → rag_retrieval_failed
      → rag_latency_ms
      → reasoning_trace
    """
    start = time.monotonic()
    logger.debug(
        "rag_retrieval_started",
        user_id=state.user_id,
        channel=state.channel,
    )

    try:
        # Embed query — sync call wrapped in thread pool
        # Prevents blocking the async event loop
        model = get_embedding_model()

        def _embed(text: str) -> list[float]:
            return model.encode(text).tolist()

        query_embedding = await asyncio.to_thread(
            _embed, state.message
        )

        # Get user-specific ChromaDB collection
        chroma = get_chroma_client()
        collection_name = (
            f"{settings.chroma_collection_name}_{state.user_id}"
        )

        def _query_chroma() -> dict[str, Any]:
            try:
                collection = chroma.get_collection(collection_name)
                return collection.query(
                    query_embeddings=[query_embedding],
                    n_results=3,
                    include=["documents", "distances"],
                )
            except Exception as e:
                raise ChromaDBException(
                    f"ChromaDB query failed: {e}",
                    user_id=state.user_id,
                    operation="query_collection",
                ) from e

        results = await asyncio.to_thread(_query_chroma)

        # Filter by similarity threshold
        # ChromaDB returns distances (lower = more similar)
        # Convert distance to similarity: similarity = 1 - distance
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        documents = list(dict.fromkeys(documents))

        relevant_chunks: list[str] = []
        for doc, distance in zip(documents, distances):
            similarity = 1 - distance
            if similarity >= 0.15:
                relevant_chunks.append(doc)
            else:
                logger.warning(
                    "rag_chunk_below_threshold",
                    similarity=round(similarity, 3),
                    threshold=0.15,
                )

        if not relevant_chunks:
            logger.warning(
                "rag_no_relevant_chunks",
                user_id=state.user_id,
                message_preview=state.message[:50],
            )

        rag_context = "\n\n---\n\n".join(relevant_chunks)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "rag_retrieval_completed",
            chunks_found=len(relevant_chunks),
            latency_ms=elapsed_ms,
        )

        return state.model_copy(update={
            "rag_context": rag_context,
            "rag_chunks_found": len(relevant_chunks),
            "rag_retrieval_failed": False,
            "rag_latency_ms": elapsed_ms,
            "reasoning_trace": [
                *state.reasoning_trace,
                {
                    "node": "retriever",
                    "chunks_found": len(relevant_chunks),
                    "latency_ms": elapsed_ms,
                    "threshold": settings.rag_similarity_threshold,
                },
            ],
        })

    except KnowledgeBaseEmptyException:
        # KB is empty — graceful degradation
        # LLM will answer from business description only
        logger.warning(
            "rag_knowledge_base_empty",
            user_id=state.user_id,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return state.model_copy(update={
            "rag_context": "",
            "rag_chunks_found": 0,
            "rag_retrieval_failed": False,  # Not a failure — just empty
            "rag_latency_ms": elapsed_ms,
        })

    except ChromaDBException as e:
        # ChromaDB infra failure — degrade gracefully
        logger.error(
            "rag_chromadb_failed",
            error=str(e),
            user_id=state.user_id,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return state.model_copy(update={
            "rag_context": "",
            "rag_chunks_found": 0,
            "rag_retrieval_failed": True,
            "rag_latency_ms": elapsed_ms,
            "reasoning_trace": [
                *state.reasoning_trace,
                {
                    "node": "retriever",
                    "error": str(e),
                    "degraded": True,
                    "latency_ms": elapsed_ms,
                },
            ],
        })

    except Exception as e:
        logger.error(
            "rag_retrieval_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return state.model_copy(update={
            "rag_context": "",
            "rag_chunks_found": 0,
            "rag_retrieval_failed": True,
            "rag_latency_ms": elapsed_ms,
        })


# ─────────────────────────────────────────────────────────────────────────
# LLM Reasoning Node
# ─────────────────────────────────────────────────────────────────────────

async def reasoner_node(state: AgentState) -> AgentState:
    """
    LangGraph Node 2: LLM Reasoning.

    Calls Groq LLM with:
    - System prompt (business context + RAG + channel guidelines)
    - Conversation history (last 5 turns)
    - Sanitized customer message (human turn)

    Structured output enforced via .with_structured_output(AIResponse).
    Retry 3x with exponential backoff on LLM failures.
    Circuit breaker on Groq — fails fast if Groq is down.

    Updates state:
      → ai_reply
      → intent
      → confidence
      → escalate
      → escalation_reason
      → lead_name / phone / email
      → llm_latency_ms
      → retry_count
      → reasoning_trace
    """
    start = time.monotonic()
    logger.debug(
        "llm_reasoning_started",
        user_id=state.user_id,
        retry_count=state.retry_count,
        rag_chunks=state.rag_chunks_found,
    )

    profile = state.business_profile

    # Build system prompt from business profile + RAG context
    system_prompt = build_system_prompt(
        business_name=profile.get("business_name", "Our Business"),
        industry=profile.get("industry", "General"),
        description=profile.get("description", ""),
        bot_tone=profile.get("bot_tone", "professional"),
        bot_language=profile.get("bot_language", "english"),
        fallback_message=profile.get(
            "fallback_message",
            "I'll connect you with our team shortly.",
        ),
        working_hours_start=profile.get("working_hours_start", "09:00"),
        working_hours_end=profile.get("working_hours_end", "18:00"),
        working_days=profile.get("working_days", "Mon-Sat"),
        rag_context=state.rag_context,
        rag_chunks_found=state.rag_chunks_found,
        channel=state.channel.value,
        escalation_threshold=profile.get("escalation_threshold", 2),
    )

    # Sanitize customer message — defense in depth
    safe_message = sanitize_customer_input(state.message)

    # Build message list with conversation history
    messages: list[Any] = [SystemMessage(content=system_prompt)]

    # Include last 5 turns for context
    for turn in state.conversation_history[-5:]:
        if turn.get("role") == "customer":
            messages.append(HumanMessage(content=turn["content"]))

    # Current message — human turn
    messages.append(HumanMessage(content=safe_message))

    # Retry decorator for LLM calls
    @retry(
        stop=stop_after_attempt(settings.agent_max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((LLMException, LLMTimeoutException)),
        before_sleep=lambda rs: log_retry_attempt(
            operation="groq_llm_call",
            attempt=rs.attempt_number,
            max_attempts=settings.agent_max_retries,
            error=str(rs.outcome.exception()),
            wait_seconds=getattr(rs.next_action, "sleep", 0),
        ),
        reraise=True,
    )
    async def _call_llm_with_retry() -> AIResponse:
        """Inner LLM call with structured output enforcement."""
        llm = _build_groq_client()
        structured_llm = llm.with_structured_output(AIResponse)

        try:
            response = await groq_circuit.call(
                structured_llm.ainvoke, messages
            )
            return response
        except CircuitOpenException as e:
            logger.error(
                "groq_circuit_open",
                retry_after=e.retry_after_seconds,
            )
            raise LLMException(
                f"Groq circuit open: {e}",
                user_id=state.user_id,
                channel=state.channel.value,
                operation="llm_call",
            ) from e
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str:
                raise LLMTimeoutException(
                    f"Groq timeout: {e}",
                    user_id=state.user_id,
                    operation="llm_call",
                ) from e
            elif "rate" in error_str or "429" in error_str:
                raise LLMRateLimitException(
                    f"Groq rate limit: {e}",
                    user_id=state.user_id,
                    operation="llm_call",
                ) from e
            elif "validation" in error_str or "parse" in error_str:
                raise LLMMalformedOutputException(
                    f"LLM output failed validation: {e}",
                    raw_output=str(e),
                    user_id=state.user_id,
                    operation="llm_call",
                ) from e
            else:
                raise LLMException(
                    f"Groq call failed: {e}",
                    user_id=state.user_id,
                    operation="llm_call",
                ) from e

    try:
        # Attempt structured LLM call
        ai_response: AIResponse = await _call_llm_with_retry()

        elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "llm_reasoning_completed",
            intent=ai_response.intent,
            confidence=ai_response.confidence,
            escalate=ai_response.escalate,
            latency_ms=elapsed_ms,
        )

        return state.model_copy(update={
            "ai_reply": ai_response.reply,
            "intent": ai_response.intent,
            "confidence": ai_response.confidence,
            "escalate": ai_response.escalate,
            "escalation_reason": ai_response.escalation_reason,
            "lead_name": ai_response.lead_name,
            "lead_phone": ai_response.lead_phone,
            "lead_email": ai_response.lead_email,
            "llm_latency_ms": elapsed_ms,
            "reasoning_trace": [
                *state.reasoning_trace,
                {
                    "node": "reasoner",
                    "intent": ai_response.intent,
                    "confidence": ai_response.confidence,
                    "escalate": ai_response.escalate,
                    "latency_ms": elapsed_ms,
                    "retry_count": state.retry_count,
                    "rag_used": state.rag_chunks_found > 0,
                },
            ],
        })

    except LLMMalformedOutputException as e:
        # One clarifying retry before giving up
        logger.warning(
            "llm_malformed_output_retrying",
            attempt=state.retry_count + 1,
            error=str(e),
        )

        if state.retry_count >= 1:
            # Already retried once — escalate
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return state.model_copy(update={
                "escalate": True,
                "escalation_reason": "llm_malformed_output_after_retry",
                "ai_reply": profile.get(
                    "fallback_message",
                    "Our team will get back to you shortly.",
                ),
                "confidence": 0.0,
                "llm_latency_ms": elapsed_ms,
                "retry_count": state.retry_count + 1,
            })

        # Build clarify prompt and retry
        clarify_prompt = build_clarify_prompt(
            original_message=safe_message,
            malformed_output=e.raw_output or "",
            business_name=profile.get("business_name", "Our Business"),
            fallback_message=profile.get(
                "fallback_message",
                "Our team will get back to you shortly.",
            ),
        )

        try:
            llm = _build_groq_client()
            structured_llm = llm.with_structured_output(AIResponse)
            clarify_messages = [
                SystemMessage(content=clarify_prompt),
                HumanMessage(content=safe_message),
            ]
            ai_response = await groq_circuit.call(
                structured_llm.ainvoke, clarify_messages
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            return state.model_copy(update={
                "ai_reply": ai_response.reply,
                "intent": ai_response.intent,
                "confidence": ai_response.confidence,
                "escalate": ai_response.escalate,
                "escalation_reason": ai_response.escalation_reason,
                "lead_name": ai_response.lead_name,
                "lead_phone": ai_response.lead_phone,
                "lead_email": ai_response.lead_email,
                "llm_latency_ms": elapsed_ms,
                "retry_count": state.retry_count + 1,
            })

        except Exception as clarify_error:
            logger.error(
                "llm_clarify_retry_failed",
                error=str(clarify_error),
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return state.model_copy(update={
                "escalate": True,
                "escalation_reason": "llm_clarify_retry_failed",
                "ai_reply": profile.get(
                    "fallback_message",
                    "Our team will get back to you shortly.",
                ),
                "confidence": 0.0,
                "llm_latency_ms": elapsed_ms,
                "retry_count": state.retry_count + 1,
            })

    except LLMException as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "llm_reasoning_failed",
            error=str(e),
            error_type=type(e).__name__,
            retry_count=state.retry_count,
            latency_ms=elapsed_ms,
        )
        return state.model_copy(update={
            "escalate": True,
            "escalation_reason": f"llm_failed: {type(e).__name__}",
            "ai_reply": profile.get(
                "fallback_message",
                "Our team will get back to you shortly.",
            ),
            "confidence": 0.0,
            "llm_latency_ms": elapsed_ms,
            "error_message": str(e),
            "retry_count": state.retry_count + 1,
        })


# ─────────────────────────────────────────────────────────────────────────
# Validator Node
# ─────────────────────────────────────────────────────────────────────────

async def validator_node(state: AgentState) -> AgentState:
    """
    LangGraph Node 3: Response Validation.

    Checks:
    1. Confidence below threshold → flag for escalation
    2. Retry count exceeded → force escalation
    3. Working hours → append suffix if outside hours
    4. Reply is not empty

    Updates state:
      → escalate (may change to True)
      → escalation_reason
      → ai_reply (may append after-hours suffix)
      → reasoning_trace
    """
    logger.debug(
        "validator_started",
        confidence=state.confidence,
        escalate=state.escalate,
        retry_count=state.retry_count,
    )

    profile = state.business_profile
    updates: dict[str, Any] = {}

    # Check 1: Confidence threshold
    if (
        not state.escalate
        and state.confidence < 0.45
    ):
        logger.warning(
            "validator_low_confidence",
            confidence=state.confidence,
            threshold=settings.escalation_confidence_threshold,
        )
        updates["escalate"] = True
        updates["escalation_reason"] = (
            f"confidence_{state.confidence:.2f}_below_"
            f"threshold_{settings.escalation_confidence_threshold}"
        )

    # Check 2: Max retries exceeded
    if state.retry_count >= state.max_retries:
        logger.warning(
            "validator_max_retries_exceeded",
            retry_count=state.retry_count,
            max_retries=state.max_retries,
        )
        updates["escalate"] = True
        updates["escalation_reason"] = (
            f"max_retries_{state.max_retries}_exceeded"
        )

    # Check 3: Empty reply
    if not state.ai_reply or not state.ai_reply.strip():
        logger.error(
            "validator_empty_reply",
            user_id=state.user_id,
        )
        updates["escalate"] = True
        updates["escalation_reason"] = "empty_reply"
        updates["ai_reply"] = profile.get(
            "fallback_message",
            "Our team will get back to you shortly.",
        )

    # Check 4: Working hours — append suffix if outside
    within_hours = _is_within_working_hours(
        working_hours_start=profile.get("working_hours_start"),
        working_hours_end=profile.get("working_hours_end"),
        timezone_str=profile.get("timezone", "Asia/Kolkata"),
    )

    if not within_hours and state.ai_reply:
        suffix = build_after_hours_suffix(
            working_hours_start=profile.get(
                "working_hours_start", "09:00"
            ),
            working_hours_end=profile.get(
                "working_hours_end", "18:00"
            ),
            working_days=profile.get("working_days", "Mon-Sat"),
        )
        current_reply = updates.get("ai_reply", state.ai_reply)
        updates["ai_reply"] = current_reply + suffix

    updates["reasoning_trace"] = [
        *state.reasoning_trace,
        {
            "node": "validator",
            "confidence": state.confidence,
            "escalate": updates.get("escalate", state.escalate),
            "within_hours": within_hours,
            "retry_count": state.retry_count,
        },
    ]

    logger.debug(
        "validator_completed",
        escalate=updates.get("escalate", state.escalate),
        within_hours=within_hours,
    )

    return state.model_copy(update=updates)


# ─────────────────────────────────────────────────────────────────────────
# Persistence Node
# ─────────────────────────────────────────────────────────────────────────

async def persistence_node(state: AgentState) -> AgentState:
    """
    LangGraph Node 4: Save Everything To Database.

    Saves atomically:
    1. conversation record
    2. inbound message (customer)
    3. outbound message (AI reply)
    4. lead (if extracted)
    5. escalation record (if needed)
    6. notification (if escalated)

    Uses atomic_save() for conversation + messages.
    Lead and escalation saved separately with full error handling.

    Updates state:
      → conversation_id
      → total_latency_ms
    """
    logger.debug(
        "persistence_started",
        user_id=state.user_id,
        channel=state.channel,
    )

    db = get_admin_db()
    total_start = time.monotonic()

    try:
        # Save conversation + both messages atomically
        conversation_data: dict[str, Any] = {
            "user_id": state.user_id,
            "channel": state.channel.value,
            "from_contact": state.from_contact,
            "status": (
                "escalated" if state.escalate else "ai_handled"
            ),
            "escalated": state.escalate,
            "resolved": False,
            "response_time_ms": state.llm_latency_ms,
            "intent": state.intent.value
            if state.intent
            else "unknown",
            "confidence": state.confidence,
            "reasoning_trace": state.reasoning_trace,
        }

        inbound_message_data: dict[str, Any] = {
            "user_id": state.user_id,
            "direction": "inbound",
            "content": state.message,
            "sent_by": "customer",
            # conversation_id added after conversation created
        }

        outbound_message_data: dict[str, Any] = {
            "user_id": state.user_id,
            "direction": "outbound",
            "content": state.ai_reply,
            "sent_by": "ai",
        }

        # Step 1: Save conversation
        conversation = await db.insert("conversations", conversation_data)
        conversation_id = conversation["id"]

        # Step 2: Save both messages with conversation_id
        inbound_message_data["conversation_id"] = conversation_id
        outbound_message_data["conversation_id"] = conversation_id

        await db.bulk_insert("messages", [
            inbound_message_data,
            outbound_message_data,
        ])

        logger.info(
            "conversation_and_messages_saved",
            conversation_id=conversation_id,
            channel=state.channel.value,
        )

        # Step 3: Save lead if extracted
        has_lead = any([
            state.lead_name,
            state.lead_phone,
            state.lead_email,
        ])

        if has_lead:
            lead_data: dict[str, Any] = {
                "user_id": state.user_id,
                "conversation_id": conversation_id,
                "name": state.lead_name,
                "phone": state.lead_phone,
                "email": state.lead_email,
                "channel": state.channel.value,
                "query": state.message[:500],
                "status": "new",
            }
            try:
                await db.insert("leads", lead_data)
                logger.info(
                    "lead_saved",
                    conversation_id=conversation_id,
                    has_name=bool(state.lead_name),
                    has_phone=bool(state.lead_phone),
                    has_email=bool(state.lead_email),
                )
            except Exception as lead_error:
                # Lead save failure should NOT stop the flow
                # Customer already got their reply
                logger.error(
                    "lead_save_failed",
                    conversation_id=conversation_id,
                    error=str(lead_error),
                )

        # Step 4: Save escalation + notification if needed
        if state.escalate:
            escalation_data: dict[str, Any] = {
                "user_id": state.user_id,
                "conversation_id": conversation_id,
                "channel": state.channel.value,
                "from_contact": state.from_contact,
                "reason": state.escalation_reason,
                "status": "open",
            }
            try:
                escalation = await db.insert(
                    "escalations", escalation_data
                )
                logger.warning(
                    "escalation_created",
                    conversation_id=conversation_id,
                    reason=state.escalation_reason,
                    escalation_id=escalation["id"],
                )

                # Notify owner
                notification_data: dict[str, Any] = {
                    "user_id": state.user_id,
                    "type": "escalation",
                    "title": "New Escalation",
                    "message": (
                        f"Customer on {state.channel.value} "
                        f"needs human assistance. "
                        f"Reason: {state.escalation_reason}"
                    ),
                    "reference_id": escalation["id"],
                    "reference_type": "escalation",
                    "read": False,
                }
                await db.insert("notifications", notification_data)

            except Exception as esc_error:
                logger.error(
                    "escalation_save_failed",
                    conversation_id=conversation_id,
                    error=str(esc_error),
                )

        total_ms = int((time.monotonic() - total_start) * 1000)

        logger.info(
            "persistence_completed",
            conversation_id=conversation_id,
            total_latency_ms=total_ms,
        )

        return state.model_copy(update={
            "conversation_id": conversation_id,
            "total_latency_ms": (
                state.llm_latency_ms
                + state.rag_latency_ms
                + total_ms
            ),
        })

    except Exception as e:
        logger.error(
            "persistence_failed",
            user_id=state.user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        # Do not raise — customer already got their reply
        # Log the failure and continue
        return state


# ─────────────────────────────────────────────────────────────────────────
# Routing functions
# ─────────────────────────────────────────────────────────────────────────

def route_after_reasoner(
    state: AgentState,
) -> Literal["validator", "validator"]:
    """
    Routes after reasoner node.
    Always goes to validator — validator decides escalation.
    """
    return "validator"


def route_after_validator(
    state: AgentState,
) -> Literal["persistence"]:
    """
    Routes after validator.
    Always persists — even escalations need to be saved.
    """
    return "persistence"


# ─────────────────────────────────────────────────────────────────────────
# Build LangGraph
# ─────────────────────────────────────────────────────────────────────────

def _build_graph() -> Any:
    """
    Builds the LangGraph StateGraph.

    Nodes:
      retriever  → RAG retrieval
      reasoner   → LLM call
      validator  → confidence + escalation check
      persistence → DB saves

    Always uses MemorySaver for development checkpointing.
    In production: swap MemorySaver for PostgresSaver.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("retriever", retriever_node)
    graph.add_node("reasoner", reasoner_node)
    graph.add_node("validator", validator_node)
    graph.add_node("persistence", persistence_node)

    # Entry point
    graph.set_entry_point("retriever")

    # Edges
    graph.add_edge("retriever", "reasoner")
    graph.add_edge("reasoner", "validator")
    graph.add_edge("validator", "persistence")
    graph.add_edge("persistence", END)

    # Compile with memory checkpointing
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Module-level compiled graph — built once
_graph = _build_graph()


# ─────────────────────────────────────────────────────────────────────────
# Public API — called by webhook services
# ─────────────────────────────────────────────────────────────────────────

async def process_message(
    user_id: str,
    channel: str,
    from_contact: str,
    message: str,
    business_profile: dict[str, Any],
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Main entry point for the AI Brain.
    Called by whatsapp.py, voice.py, email_handler.py.

    Flow:
      retriever → reasoner → validator → persistence

    Args:
        user_id: Business owner's user_id
        channel: whatsapp / voice / email
        from_contact: Customer's phone/email
        message: Customer's message (raw — sanitized inside)
        business_profile: Full business_profile dict from DB
        conversation_history: Last 5 turns [[role, content], ...]

    Returns:
        dict with:
          reply: str — what to send back to customer
          escalated: bool — whether human needed
          conversation_id: str — for tracking
          total_latency_ms: int
    """
    thread_id = str(uuid.uuid4())

    initial_state = AgentState(
        user_id=user_id,
        channel=ChannelType(channel),
        from_contact=from_contact,
        message=message,
        business_profile=business_profile,
        conversation_history=conversation_history or [],
        max_retries=settings.agent_max_retries,
    )

    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": settings.agent_max_iterations,
    }

    logger.info(
        "ai_brain_processing_started",
        user_id=user_id,
        channel=channel,
        thread_id=thread_id,
    )

    try:
        final_state = await _graph.ainvoke(
            initial_state,
            config=config,
        )
        # LangGraph returns dict-like state
        if not isinstance(final_state, AgentState):
            final_state = AgentState(**final_state)

        logger.info(
            "ai_brain_processing_completed",
            user_id=user_id,
            channel=channel,
            thread_id=thread_id,
            escalated=final_state.escalate,
            confidence=final_state.confidence,
            total_latency_ms=final_state.total_latency_ms,
        )

        return {
            "reply": final_state.ai_reply,
            "escalated": final_state.escalate,
            "conversation_id": final_state.conversation_id,
            "intent": (
                final_state.intent.value
                if final_state.intent
                else "unknown"
            ),
            "confidence": final_state.confidence,
            "total_latency_ms": final_state.total_latency_ms,
            "lead_captured": any([
                final_state.lead_name,
                final_state.lead_phone,
                final_state.lead_email,
            ]),
        }
       

    except Exception as e:
        logger.error(
            "ai_brain_processing_failed",
            user_id=user_id,
            channel=channel,
            thread_id=thread_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        # Return fallback — never crash the webhook handler
        fallback = business_profile.get(
            "fallback_message",
            "Our team will get back to you shortly.",
        )
        return {
            "reply": fallback,
            "escalated": True,
            "conversation_id": None,
            "intent": "unknown",
            "confidence": 0.0,
            "total_latency_ms": 0,
            "lead_captured": False,
        }