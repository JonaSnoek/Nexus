from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.models.user import User, UserPermission, Permission, Usage


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
) -> User:
    user = User(
        username=username,
        hashed_password=get_password_hash(password) if password else None,
        email=email,
        display_name=display_name or username,
        role=role,
        is_sso=is_sso,
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


async def get_or_create_usage(db: AsyncSession, user_id: int, date_str: str) -> Usage:
    result = await db.execute(select(Usage).where(Usage.user_id == user_id, Usage.date == date_str))
    usage = result.scalar_one_or_none()
    if not usage:
        usage = Usage(user_id=user_id, date=date_str, tokens_used=0, messages_used=0)
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
    return usage


async def check_token_limit(db: AsyncSession, user: User) -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await get_or_create_usage(db, user.id, today)
    return usage.tokens_used < user.daily_token_limit


async def check_message_limit(db: AsyncSession, user: User) -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await get_or_create_usage(db, user.id, today)
    return usage.messages_used < user.daily_message_limit


async def increment_usage(db: AsyncSession, user_id: int, tokens: int = 0, messages: int = 0) -> Usage:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await get_or_create_usage(db, user_id, today)
    usage.tokens_used += tokens
    usage.messages_used += messages
    await db.commit()
    await db.refresh(usage)
    return usage
