from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User, UserRole, Permission, UserPermission, Usage
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListResponse,
    PermissionResponse, UsageResponse, UpdatePermissionsRequest, UpdateLimitsRequest,
)
from app.services.user_service import (
    get_user_by_id, get_user_by_username, create_user, update_user,
    list_users, count_users,
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
        "daily_token_limit": user.daily_token_limit,
        "daily_message_limit": user.daily_message_limit,
    }


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
    serialized = [_serialize_user(u) for u in users]
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
    return _serialize_user(user)


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

    update_data = body.model_dump(exclude_unset=True)
    user = await update_user(db, user, **update_data)
    await log_action(db, "limits_updated", user_id=current_user.id, details=f"Updated limits for user {user_id}")
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
        select(Usage).where(Usage.user_id == user_id).order_by(Usage.date.desc()).limit(30)
    )
    usage_records = result.scalars().all()
    return [UsageResponse(date=u.date, tokens_used=u.tokens_used, messages_used=u.messages_used) for u in usage_records]