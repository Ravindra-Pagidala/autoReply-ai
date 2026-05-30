from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def get_lead_recommendation(lead: dict[str, Any]) -> dict[str, str] | None:
    """
    Returns a recommended next action for a lead based on
    temperature, contact info, status, and age.
    Called at query time so time-based rules (e.g. >24h) are always fresh.
    """
    status = lead.get("status", "new")
    if status in ("resolved", "lost"):
        return None

    created_at = lead.get("created_at")
    hours_old = 0.0
    if created_at:
        try:
            dt = (
                created_at
                if isinstance(created_at, datetime)
                else datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours_old = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except (ValueError, TypeError):
            pass

    temperature = lead.get("lead_temperature") or "cold"
    phone       = lead.get("phone")
    email       = lead.get("email")
    score       = lead.get("lead_score") or 0

    if temperature == "hot":
        if phone:
            return {"label": "Call Now",    "icon": "📞", "priority": "high"}
        if email:
            return {"label": "Email Now",   "icon": "📧", "priority": "high"}
        return     {"label": "Get Contact", "icon": "🎯", "priority": "high"}

    if temperature == "warm":
        if status == "follow_up":
            return {"label": "Check In",    "icon": "💬", "priority": "medium"}
        if hours_old > 24:
            return {"label": "Follow Up",   "icon": "⏰", "priority": "medium"}
        return     {"label": "Send Details","icon": "📨", "priority": "medium"}

    # cold
    if score == 0:
        return {"label": "Qualify Lead", "icon": "❓", "priority": "low"}
    return     {"label": "Low Priority", "icon": "❄️", "priority": "low"}
