from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.models.user import User, UserPermission, Permission, Usage
from app.services.settings_service import get_default_limits

CURRENT_PERIOD = lambda: datetime.now(timezone.utc).strftime("%Y-%m")


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    role: str = "USER",
    is_sso: bool = False,
    monthly_token_limit: Optional[int] = None,
    monthly_message_limit: Optional[int] = None,
) -> User:
    defaults = await get_default_limits(db)
    user = User(
        username=username,
        hashed_password=get_password_hash(password) if password else None,
        email=email,
        display_name=display_name or username,
        role=role,
        is_sso=is_sso,
        monthly_token_limit=monthly_token_limit if monthly_token_limit is not None else defaults["default_token_limit"],
        monthly_message_limit=monthly_message_limit if monthly_message_limit is not None else defaults["default_message_limit"],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user: User, **kwargs) -> User:
    for key, value in kwargs.items():
        if value is not None and hasattr(user, key):
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await db.execute(select(User).offset(skip).limit(limit).order_by(User.id))
    return list(result.scalars().all())


async def count_users(db: AsyncSession) -> int:
    result = await db.execute(select(func.count(User.id)))
    return result.scalar()


async def check_permission(db: AsyncSession, user_id: int, permission_name: str) -> bool:
    user = await get_user_by_id(db, user_id)
    if user and user.role == "ADMIN":
        return True
    result = await db.execute(
        select(UserPermission)
        .join(Permission, Permission.id == UserPermission.permission_id)
        .where(UserPermission.user_id == user_id, Permission.name == permission_name)
    )
    return result.scalar_one_or_none() is not None


async def get_or_create_usage(db: AsyncSession, user_id: int, period: Optional[str] = None) -> Usage:
    period = period or CURRENT_PERIOD()
    result = await db.execute(select(Usage).where(Usage.user_id == user_id, Usage.period == period))
    usage = result.scalar_one_or_none()
    if not usage:
        usage = Usage(user_id=user_id, period=period, tokens_used=0, messages_used=0)
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
    return usage


async def check_token_limit(db: AsyncSession, user: User) -> bool:
    usage = await get_or_create_usage(db, user.id)
    return usage.tokens_used < user.monthly_token_limit


async def check_message_limit(db: AsyncSession, user: User) -> bool:
    usage = await get_or_create_usage(db, user.id)
    return usage.messages_used < user.monthly_message_limit


async def increment_usage(db: AsyncSession, user_id: int, tokens: int = 0, messages: int = 0) -> Usage:
    usage = await get_or_create_usage(db, user_id)
    usage.tokens_used += tokens
    usage.messages_used += messages
    await db.commit()
    await db.refresh(usage)
    return usage


async def get_monthly_summary(db: AsyncSession, user: User) -> dict:
    usage = await get_or_create_usage(db, user.id)
    return {
        "period": usage.period,
        "tokens_used_month": usage.tokens_used,
        "messages_used_month": usage.messages_used,
        "monthly_token_limit": user.monthly_token_limit,
        "monthly_message_limit": user.monthly_message_limit,
        "tokens_remaining_month": max(user.monthly_token_limit - usage.tokens_used, 0),
        "messages_remaining_month": max(user.monthly_message_limit - usage.messages_used, 0),
    }
