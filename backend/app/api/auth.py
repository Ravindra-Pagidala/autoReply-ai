from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.utils.exceptions import InvalidTokenException
from app.utils.logger import get_logger
from app.models.database import get_admin_db, get_user_db
from app.schemas.base import (
    BusinessProfileCreate,
    BusinessProfileResponse,
    BusinessProfileUpdate,
    SuccessResponse,
    TeamMemberInvite,
    TeamMemberResponse,
    TeamMemberUpdate,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """
    Dependency — extracts and validates JWT token.
    Used by all protected endpoints via Depends(get_current_user).
    Returns user dict with id, email.
    """
    token = credentials.credentials
    try:
        from app.models.database import get_admin_client
        client = get_admin_client()
        user_response = client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise InvalidTokenException(
                "Invalid or expired token",
                operation="get_current_user",
            )
        return {
            "id": user_response.user.id,
            "email": user_response.user.email,
            "token": token,
        }
    except InvalidTokenException:
        raise
    except Exception as e:
        logger.error("token_validation_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token") from e


@router.get("/me")
async def get_me(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns current user info + business profile."""
    db = get_admin_db()
    profile = await db.get_by_field(
        "business_profiles", "user_id", user["id"]
    )
    return {
        "user": {"id": user["id"], "email": user["email"]},
        "profile": BusinessProfileResponse(**profile).model_dump()
        if profile else None,
    }


@router.post("/profile", response_model=BusinessProfileResponse)
async def create_or_update_profile(
    body: BusinessProfileCreate,
    user: dict[str, Any] = Depends(get_current_user),
) -> BusinessProfileResponse:
    """Creates or updates business profile (onboarding step 1)."""
    db = get_admin_db()
    data = body.model_dump(exclude_none=True)
    data["user_id"] = user["id"]
    data["onboarding_step"] = 2
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    record = await db.upsert("business_profiles", data, on_conflict="user_id")
    return BusinessProfileResponse(**record)


@router.patch("/profile", response_model=BusinessProfileResponse)
async def update_profile(
    body: BusinessProfileUpdate,
    user: dict[str, Any] = Depends(get_current_user),
) -> BusinessProfileResponse:
    """Updates business profile settings."""
    db = get_admin_db()
    existing = await db.get_by_field(
        "business_profiles", "user_id", user["id"]
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    data = body.model_dump(exclude_none=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    record = await db.update("business_profiles", existing["id"], data)
    return BusinessProfileResponse(**record)


@router.post("/profile/complete-onboarding", response_model=SuccessResponse)
async def complete_onboarding(
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Marks onboarding as complete. Called after step 3 (KB upload)."""
    db = get_admin_db()
    existing = await db.get_by_field(
        "business_profiles", "user_id", user["id"]
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    await db.update("business_profiles", existing["id"], {
        "onboarding_completed": True,
        "onboarding_step": 4,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return SuccessResponse(message="Onboarding complete")


# ── Team Members ──────────────────────────────────────────────────────────

@router.post("/team/invite", response_model=TeamMemberResponse)
async def invite_team_member(
    body: TeamMemberInvite,
    user: dict[str, Any] = Depends(get_current_user),
) -> TeamMemberResponse:
    """Owner invites a team member by email."""
    db = get_admin_db()

    # Check not already invited
    existing = await db.get_by_field(
        "team_members", "member_email", body.member_email
    )
    if existing and existing.get("owner_id") == user["id"]:
        raise HTTPException(status_code=409, detail="Member already invited")

    record = await db.insert("team_members", {
        "owner_id": user["id"],
        "member_email": body.member_email,
        "role": body.role,
        "status": "pending",
    })
    return TeamMemberResponse(**record)


@router.get("/team", response_model=list[TeamMemberResponse])
async def list_team_members(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[TeamMemberResponse]:
    """Lists all team members for current owner."""
    db = get_admin_db()
    from app.models.database import Filter, FilterOperator
    rows = await db.list_records(
        "team_members",
        filters=[Filter("owner_id", FilterOperator.EQ, user["id"])],
        page_size=50,
    )
    return [TeamMemberResponse(**r) for r in rows]


@router.patch("/team/{member_id}", response_model=SuccessResponse)
async def update_team_member(
    member_id: str,
    body: TeamMemberUpdate,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Owner updates team member role."""
    db = get_admin_db()
    await db.update("team_members", member_id, {"role": body.role})
    return SuccessResponse(message="Role updated")


@router.delete("/team/{member_id}", response_model=SuccessResponse)
async def remove_team_member(
    member_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> SuccessResponse:
    """Owner removes a team member."""
    db = get_admin_db()
    await db.delete("team_members", member_id)
    return SuccessResponse(message="Team member removed")