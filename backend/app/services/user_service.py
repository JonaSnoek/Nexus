import json
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy import select, func, insert as generic_insert, update as sa_update, delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.models.user import User, UserPermission, Permission, Usage, UsageEvent
from app.services.settings_service import get_default_limits

CURRENT_PERIOD = lambda: datetime.now(timezone.utc).strftime("%Y-%m")


class LimitExceededError(Exception):
    """Raised when a charge would exceed the user's effective monthly quota."""

    def __init__(
        self,
        action_type: str,
        cost: int,
        limit: Optional[int] = None,
        used: int = 0,
    ):
        super().__init__(f"Limit exceeded for {action_type}")
        self.action_type = action_type
        self.cost = cost
        self.limit = limit
        self.used = used

    @property
    def remaining(self) -> Optional[int]:
        if self.limit is None:
            return None
        return max(self.limit - self.used, 0)


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


# ---------------------------------------------------------------------------
# Effective per-user token limit
# ---------------------------------------------------------------------------

async def get_effective_token_limit(
    db: AsyncSession,
    user: User,
    default_token_limit: Optional[int] = None,
) -> Optional[int]:
    """Return the token quota the user must respect, or None when unlimited.

    Three states (see also the admin UI "Nutzung & Limits"):
      A. standard default: user uses the global default_token_limit.
      B. custom limit:     limits_exempt + custom_monthly_token_limit.
      C. unlimited:        limits_exempt + unlimited -> never blocked.
    """
    if user.unlimited:
        return None
    if user.limits_exempt:
        if user.custom_monthly_token_limit is not None:
            return user.custom_monthly_token_limit
        # Exempt without a custom value is a broken half-configuration;
        # never treat it as unlimited - fall back to the global default.
    if default_token_limit is None:
        defaults = await get_default_limits(db)
        default_token_limit = defaults["default_token_limit"]
    return default_token_limit


# ---------------------------------------------------------------------------
# Atomic charge (check + book)
# ---------------------------------------------------------------------------

async def spend_user_usage(
    db: AsyncSession,
    user: User,
    action_type: str,
    tokens: int,
    metadata: Optional[dict] = None,
) -> UsageEvent:
    """Charge the user's monthly quota for an action.

    The check and the booking happen in a single atomic UPSERT guarded by a
    ``tokens_used + tokens <= limit`` WHERE clause, so parallel requests can
    never jointly overspend the quota (race condition safe).

    Unlimited users are never blocked; the charge is still recorded for
    statistics/transparency.

    Raises ``LimitExceededError`` when the remaining quota is insufficient.
    """
    period = CURRENT_PERIOD()
    limit = await get_effective_token_limit(db, user)

    # No existing usage row for this period -> the counter is zero.
    if limit is not None and tokens > limit:
        raise LimitExceededError(action_type, tokens, limit=limit, used=0)

    usage_table = Usage.__table__
    guard = (usage_table.c.tokens_used + tokens <= limit) if limit is not None else None
    dialect = db.bind.dialect.name if getattr(db, "bind", None) is not None else "sqlite"
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert
    stmt = (
        insert_fn(usage_table)
        .values(user_id=user.id, period=period, tokens_used=tokens, messages_used=0)
        .on_conflict_do_update(
            index_elements=["user_id", "period"],
            set_={"tokens_used": usage_table.c.tokens_used + tokens},
            where=guard,
        )
    )
    result = await db.execute(stmt)
    if result.rowcount != 1:
        # The guard rejected the upsert (quota exhausted). Refresh the counter
        # for an accurate error payload.
        usage_row = (
            await db.execute(
                select(Usage).where(Usage.user_id == user.id, Usage.period == period)
            )
        ).scalar_one_or_none()
        used = usage_row.tokens_used if usage_row else 0
        raise LimitExceededError(action_type, tokens, limit=limit, used=used)

    event = UsageEvent(
        user_id=user.id,
        action_type=action_type,
        tokens=tokens,
        period=period,
        details=json.dumps(metadata) if metadata else None,
    )
    db.add(event)

    try:
        await db.commit()
    except IntegrityError:
        # Extremely unlikely: a competing first-spend inserted a usage row.
        # The UPSERT above already serializes this, so treat as a failure.
        await db.rollback()
        raise
    return event


async def check_token_limit(db: AsyncSession, user: User) -> bool:
    """Backward-compatible helper: True when the quota allows another charge."""
    limit = await get_effective_token_limit(db, user)
    if limit is None:
        return True
    usage = await get_or_create_usage(db, user.id)
    return usage.tokens_used < limit


async def refund_user_usage(db: AsyncSession, user: User, event: UsageEvent) -> None:
    """Atomically reverse a reserved charge after a failed action.

    Used when image generation fails: the quota was reserved before the
    expensive work started (race condition safety) and is now returned so the
    user never pays for a failed generation. The reservation UsageEvent row is
    deleted so no bogus "successful" action stays in the ledger.
    """
    if event is None or not event.tokens:
        return
    period = event.period or CURRENT_PERIOD()
    usage_table = Usage.__table__
    stmt = (
        sa_update(usage_table)
        .where(
            usage_table.c.user_id == user.id,
            usage_table.c.period == period,
            usage_table.c.tokens_used >= event.tokens,
        )
        .values(tokens_used=usage_table.c.tokens_used - event.tokens)
    )
    await db.execute(stmt)
    await db.execute(sa_delete(UsageEvent).where(UsageEvent.id == event.id))
    await db.commit()


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


# ---------------------------------------------------------------------------
# Usage views (shared by /me, user list, admin limits)
# ---------------------------------------------------------------------------

async def _usage_action_counts(
    db: AsyncSession,
    user_id: int,
    period: str,
) -> Dict[str, int]:
    result = await db.execute(
        select(UsageEvent.action_type, func.count(UsageEvent.id))
        .where(UsageEvent.user_id == user_id, UsageEvent.period == period)
        .group_by(UsageEvent.action_type)
    )
    return {action: count for action, count in result.all()}


async def usage_view_for_user(
    db: AsyncSession,
    user: User,
    default_token_limit: Optional[int] = None,
    usage: Optional[Usage] = None,
    action_counts: Optional[Dict[str, int]] = None,
) -> dict:
    """Assemble the usage/limit view for a single user without side effects."""
    if default_token_limit is None:
        defaults = await get_default_limits(db)
        default_token_limit = defaults["default_token_limit"]

    if usage is None:
        period = CURRENT_PERIOD()
        result = await db.execute(
            select(Usage).where(Usage.user_id == user.id, Usage.period == period)
        )
        usage = result.scalar_one_or_none()

    period = usage.period if usage else CURRENT_PERIOD()
    used = usage.tokens_used if usage else 0
    messages_used = usage.messages_used if usage else 0

    if action_counts is None:
        action_counts = await _usage_action_counts(db, user.id, period)

    effective_limit = await get_effective_token_limit(db, user, default_token_limit)

    has_limit = effective_limit is not None
    if has_limit:
        remaining = max(effective_limit - used, 0)
        percent = round(used / effective_limit * 100) if effective_limit > 0 else (100 if used else 0)
    else:
        remaining = None
        percent = None

    return {
        "period": period,
        "tokens_used_month": used,
        "messages_used_month": messages_used,
        # Compat fields (existing UI/API consumers):
        "monthly_token_limit": effective_limit if has_limit else user.monthly_token_limit,
        "monthly_message_limit": user.monthly_message_limit,
        "tokens_remaining_month": remaining,
        "messages_remaining_month": max(user.monthly_message_limit - messages_used, 0),
        # New engineered fields:
        "limits_exempt": bool(user.limits_exempt),
        "custom_monthly_token_limit": user.custom_monthly_token_limit,
        "unlimited": bool(user.unlimited),
        "has_token_limit": has_limit,
        "effective_token_limit": effective_limit,
        "tokens_remaining": remaining,
        "used_percent": percent,
        # Per-action breakdown for the current period (CHAT_MESSAGE,
        # IMAGE_GENERATION, ...). Extensible for future action types.
        "action_counts": action_counts,
        "images_used_month": action_counts.get("IMAGE_GENERATION", 0),
        "chat_messages_count_month": action_counts.get("CHAT_MESSAGE", 0),
    }


async def usage_views_for_users(
    db: AsyncSession,
    users: List[User],
) -> Dict[int, dict]:
    """Batch usage view for a list of users (no row creation, no commits)."""
    if not users:
        return {}
    defaults = await get_default_limits(db)
    default_token_limit = defaults["default_token_limit"]
    period = CURRENT_PERIOD()

    ids = [u.id for u in users]
    result = await db.execute(
        select(Usage).where(Usage.user_id.in_(ids), Usage.period == period)
    )
    usage_map = {row.user_id: row for row in result.scalars().all()}

    if ids:
        count_result = await db.execute(
            select(UsageEvent.user_id, UsageEvent.action_type, func.count(UsageEvent.id))
            .where(UsageEvent.user_id.in_(ids), UsageEvent.period == period)
            .group_by(UsageEvent.user_id, UsageEvent.action_type)
        )
        counts_map: Dict[int, Dict[str, int]] = {}
        for uid, action, count in count_result.all():
            counts_map.setdefault(uid, {})[action] = count
    else:
        counts_map = {}

    views = {}
    for user in users:
        views[user.id] = await usage_view_for_user(
            db, user, default_token_limit, usage_map.get(user.id), counts_map.get(user.id, {})
        )
    return views


async def get_monthly_summary(db: AsyncSession, user: User) -> dict:
    """Legacy wrapper: ensures a usage row exists and returns the full view."""
    usage = await get_or_create_usage(db, user.id)
    return await usage_view_for_user(db, user, usage=usage)