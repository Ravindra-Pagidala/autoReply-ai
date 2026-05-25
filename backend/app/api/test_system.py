from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.utils.logger import get_logger
from app.models.database import Filter, FilterOperator, get_admin_db
from app.schemas.base import TestRunRequest, TestRunResponse, TestResultResponse
from app.agents.ai_brain import process_message
from app.api.auth import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/test", tags=["test-system"])

# Sample test messages fired during automated test runs
_TEST_MESSAGES = {
    "whatsapp": [
        "Hi, what are your services?",
        "What are your pricing plans?",
        "How do I get started?",
        "Do you offer a free trial?",
        "What are your working hours?",
        "How can I contact support?",
        "Can I book an appointment?",
        "What payment methods do you accept?",
        "Do you have any offers?",
        "Tell me more about your business.",
    ],
    "voice": [
        "What services do you provide?",
        "How much does it cost?",
        "I want to book an appointment.",
        "What are your timings?",
        "Can I speak to someone?",
    ],
    "email": [
        "I would like to know more about your pricing.",
        "Can you send me details about your services?",
        "I am interested in booking a demo.",
        "What are the features included in your plans?",
        "Please send me your contact details.",
        "I have a question about your refund policy.",
        "Can I get a custom quote?",
        "Do you offer enterprise plans?",
        "I need support for my account.",
        "How do I get started with your service?",
    ],
}


@router.post("/run", response_model=TestRunResponse)
async def run_test(
    body: TestRunRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> TestRunResponse:
    """
    Fires automated test messages across channels simultaneously.
    Shows real response times and success rates.
    This is the WOW factor for the hackathon demo.
    """
    db = get_admin_db()
    user_id = user["id"]

    # Load business profile
    profile = await db.get_by_field(
        "business_profiles", "user_id", user_id
    )
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Business profile not found")

    # Create test run record
    test_run = await db.insert("test_runs", {
        "user_id": user_id,
        "test_type": body.test_type,
        "triggered_by": "manual",
        "status": "running",
        "total_sent": 0,
        "total_success": 0,
        "total_failed": 0,
        "whatsapp_sent": 0,
        "whatsapp_success": 0,
        "voice_sent": 0,
        "voice_success": 0,
        "email_sent": 0,
        "email_success": 0,
    })
    test_run_id = test_run["id"]

    logger.info(
        "test_run_started",
        user_id=user_id,
        test_run_id=test_run_id,
        test_type=body.test_type,
    )

    # Build test tasks based on test_type
    tasks: list[tuple[str, str]] = []

    if body.test_type in ("all", "whatsapp"):
        msgs = _TEST_MESSAGES["whatsapp"][:body.whatsapp_count]
        tasks.extend([("whatsapp", m) for m in msgs])

    if body.test_type in ("all", "voice"):
        msgs = _TEST_MESSAGES["voice"][:body.voice_count]
        tasks.extend([("voice", m) for m in msgs])

    if body.test_type in ("all", "email"):
        msgs = _TEST_MESSAGES["email"][:body.email_count]
        tasks.extend([("email", m) for m in msgs])

    # Fire all tasks concurrently
    results = await asyncio.gather(*[
        _run_single_test(
            user_id=user_id,
            channel=channel,
            message=message,
            business_profile=profile,
            test_run_id=test_run_id,
        )
        for channel, message in tasks
    ], return_exceptions=True)

    # Aggregate results
    test_results: list[dict[str, Any]] = []
    success_count = 0
    fail_count = 0
    total_ms = 0
    leads_captured = 0
    channel_counts: dict[str, dict[str, int]] = {
        "whatsapp": {"sent": 0, "success": 0},
        "voice": {"sent": 0, "success": 0},
        "email": {"sent": 0, "success": 0},
    }

    for i, result in enumerate(results):
        channel, message = tasks[i]
        channel_counts[channel]["sent"] += 1

        if isinstance(result, Exception):
            fail_count += 1
            test_results.append({
                "test_run_id": test_run_id,
                "user_id": user_id,
                "channel": channel,
                "message_sent": message,
                "reply_received": None,
                "response_time_ms": 0,
                "success": False,
                "error_reason": str(result),
            })
        else:
            success_count += 1
            channel_counts[channel]["success"] += 1
            total_ms += result.get("response_time_ms", 0)
            if result.get("lead_captured"):
                leads_captured += 1
            test_results.append({
                "test_run_id": test_run_id,
                "user_id": user_id,
                "channel": channel,
                "message_sent": message,
                "reply_received": result.get("reply", ""),
                "response_time_ms": result.get("response_time_ms", 0),
                "success": True,
                "error_reason": None,
            })

    # Bulk save test results
    if test_results:
        await db.bulk_insert("test_results", test_results)

    avg_ms = total_ms // success_count if success_count > 0 else 0
    total_sent = len(tasks)

    # Update test run with final stats
    updated = await db.update("test_runs", test_run_id, {
        "status": "completed",
        "total_sent": total_sent,
        "total_success": success_count,
        "total_failed": fail_count,
        "whatsapp_sent": channel_counts["whatsapp"]["sent"],
        "whatsapp_success": channel_counts["whatsapp"]["success"],
        "voice_sent": channel_counts["voice"]["sent"],
        "voice_success": channel_counts["voice"]["success"],
        "email_sent": channel_counts["email"]["sent"],
        "email_success": channel_counts["email"]["success"],
        "avg_response_ms": avg_ms,
        "leads_captured": leads_captured,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(
        "test_run_completed",
        test_run_id=test_run_id,
        total_sent=total_sent,
        success=success_count,
        failed=fail_count,
        avg_ms=avg_ms,
    )

    return TestRunResponse(**updated)


async def _run_single_test(
    user_id: str,
    channel: str,
    message: str,
    business_profile: dict[str, Any],
    test_run_id: str,
) -> dict[str, Any]:
    """Fires a single test message through AI brain and returns result."""
    start = time.monotonic()
    result = await process_message(
        user_id=user_id,
        channel=channel,
        from_contact=f"test_{uuid.uuid4().hex[:8]}@autoreply.test",
        message=message,
        business_profile=business_profile,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return {
        "reply": result.get("reply", ""),
        "response_time_ms": elapsed_ms,
        "lead_captured": result.get("lead_captured", False),
    }


@router.get("/runs", response_model=list[TestRunResponse])
async def list_test_runs(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[TestRunResponse]:
    """Lists all test runs for current user."""
    db = get_admin_db()
    rows = await db.list_records(
        "test_runs",
        filters=[Filter("user_id", FilterOperator.EQ, user["id"])],
        page_size=20,
    )
    return [TestRunResponse(**r) for r in rows]


@router.get("/runs/{test_run_id}/results", response_model=list[TestResultResponse])
async def get_test_results(
    test_run_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[TestResultResponse]:
    """Gets individual message results for a test run."""
    db = get_admin_db()
    rows = await db.list_records(
        "test_results",
        filters=[
            Filter("test_run_id", FilterOperator.EQ, test_run_id),
            Filter("user_id", FilterOperator.EQ, user["id"]),
        ],
        page_size=100,
        order_by="created_at",
        ascending=True,
    )
    return [TestResultResponse(**r) for r in rows]