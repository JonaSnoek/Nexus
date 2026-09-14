from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User, UserRole, Permission, UserPermission, Usage, UsageEvent
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListResponse,
    PermissionResponse, UsageResponse, UsageEventResponse,
    UpdatePermissionsRequest, UpdateLimitsRequest,
)
from app.services.user_service import (
    get_user_by_id, get_user_by_username, create_user, update_user,
    list_users, count_users, usage_views_for_users, usage_view_for_user,
    CURRENT_PERIOD,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/users", tags=["users"])


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def _normalize_role(role: str) -> str:
    return "ADMIN" if role.lower() == "admin" else "USER"


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role.value.lower() if isinstance(user.role, UserRole) else str(user.role).lower(),
        "is_active": user.is_active,
        "is_sso": user.is_sso,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "monthly_token_limit": user.monthly_token_limit,
        "monthly_message_limit": user.monthly_message_limit,
        "limits_exempt": bool(user.limits_exempt),
        "custom_monthly_token_limit": user.custom_monthly_token_limit,
        "unlimited": bool(user.unlimited),
    }


def _normalize_limit_update(update_data: dict) -> dict:
    """Enforce the three-state invariants server-side (never trust the client).

    State A: limits_exempt=False  -> standard (global) limit.
    State B: limits_exempt=True + custom_monthly_token_limit -> custom limit.
    State C: limits_exempt=True + unlimited=True -> never blocked.

    Invalid combinations (e.g. unlimited=True together with an active custom
    value) are resolved deterministically.
    """
    exempt = update_data.get("limits_exempt")
    unlimited = update_data.get("unlimited")
    custom = update_data.get("custom_monthly_token_limit")

    if unlimited is True:
        update_data["limits_exempt"] = True
        update_data["custom_monthly_token_limit"] = None
        return update_data

    if exempt is False:
        update_data["unlimited"] = False
        update_data["custom_monthly_token_limit"] = None
        return update_data

    if exempt is True:
        if custom is not None:
            update_data["unlimited"] = False
        return update_data

    # exempt was not provided: only allow a custom value to activate the
    # exempt state, never as silent half-configuration.
    if custom is not None:
        update_data["limits_exempt"] = True
        update_data["unlimited"] = False
        update_data["custom_monthly_token_limit"] = custom
        return update_data

    return update_data


@router.get("/", response_model=UserListResponse)
async def list_all_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    users = await list_users(db, skip, limit)
    total = await count_users(db)
    views = await usage_views_for_users(db, users)
    serialized = []
    for u in users:
        entry = _serialize_user(u)
        entry.update(views.get(u.id, {}))
        serialized.append(entry)
    return UserListResponse(users=serialized, total=total)


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user) and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    entry = _serialize_user(user)
    entry.update(await usage_view_for_user(db, user))
    return entry


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_new_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
    user = await create_user(
        db,
        username=body.username,
        password=body.password,
        email=body.email,
        display_name=body.display_name,
        role=_normalize_role(body.role or "USER"),
        monthly_token_limit=body.monthly_token_limit,
        monthly_message_limit=body.monthly_message_limit,
    )
    await log_action(db, "user_created", user_id=current_user.id, details=f"Created user {body.username}")
    return _serialize_user(user)


@router.put("/{user_id}")
async def update_existing_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    update_data = body.model_dump(exclude_unset=True)
    if "role" in update_data and update_data["role"]:
        update_data["role"] = _normalize_role(update_data["role"])
    user = await update_user(db, user, **update_data)
    await log_action(db, "user_updated", user_id=current_user.id, details=f"Updated user {user_id}")
    return _serialize_user(user)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = False
    await db.commit()
    await log_action(db, "user_deactivated", user_id=current_user.id, details=f"Deactivated user {user_id}")
    return {"detail": "User deactivated"}


@router.put("/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    body: UpdatePermissionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(select(UserPermission).where(UserPermission.user_id == user_id))
    for up in result.scalars().all():
        await db.delete(up)

    for perm_id in body.permission_ids:
        up = UserPermission(user_id=user_id, permission_id=perm_id)
        db.add(up)

    await db.commit()
    await log_action(db, "permissions_updated", user_id=current_user.id, details=f"Updated permissions for user {user_id}")
    return {"detail": "Permissions updated"}


@router.put("/{user_id}/limits")
async def update_user_limits(
    user_id: int,
    body: UpdateLimitsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = _normalize_limit_update(body.model_dump(exclude_unset=True))

    # Keep the legacy monthly_token_limit snapshot in sync when a custom quota
    # is configured, so older consumers keep seeing a sensible number.
    if update_data.get("custom_monthly_token_limit") is not None:
        update_data["monthly_token_limit"] = update_data["custom_monthly_token_limit"]

    # Apply directly (unlike update_user, None must clear values when the
    # admin switches a user back to the standard / unlimited state).
    for key, value in update_data.items():
        if hasattr(user, key):
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    await log_action(
        db, "limits_updated", user_id=current_user.id,
        details=(
            f"Updated limits for user {user_id}: exempt={user.limits_exempt}, "
            f"custom={user.custom_monthly_token_limit}, unlimited={user.unlimited}"
        ),
    )
    return {"detail": "Limits updated"}


@router.get("/{user_id}/usage", response_model=List[UsageResponse])
async def get_user_usage(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user) and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(Usage).where(Usage.user_id == user_id).order_by(Usage.period.desc()).limit(24)
    )
    usage_records = result.scalars().all()
    return [
        UsageResponse(period=u.period, tokens_used=u.tokens_used, messages_used=u.messages_used)
        for u in usage_records
    ]


@router.get("/{user_id}/usage/events", response_model=List[UsageEventResponse])
async def get_user_usage_events(
    user_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Usage ledger entries for one user (admin or the user themself)."""
    if not _is_admin(current_user) and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    limit = min(max(limit, 1), 500)
    result = await db.execute(
        select(UsageEvent)
        .where(UsageEvent.user_id == user_id)
        .order_by(UsageEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [
        UsageEventResponse(
            id=e.id,
            action_type=e.action_type,
            tokens=e.tokens,
            period=e.period,
            created_at=e.created_at,
            metadata=e.details,
        )
        for e in events
    ]