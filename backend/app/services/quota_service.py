"""Shared server-side quota helpers used by every quota-reaching action.

Both chat messages and image generation must run through the exact same
reservation + atomic charge flow so the effectively enforced limit is always
consistent (definition of done: "Chat und Bildgenerierung müssen dieselbe
zentrale Limitlogik verwenden").
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.settings_service import get_cost_for_action
from app.services.user_service import spend_user_usage, LimitExceededError

_ACTION_LABELS = {
    "CHAT_MESSAGE": "diese Nachricht",
    "IMAGE_GENERATION": "diese Bildgenerierung",
}


def build_limit_error(action_type: str, cost: int, limit, used: int) -> dict:
    remaining = max(limit - used, 0) if limit is not None else None
    label = _ACTION_LABELS.get(action_type, "diese Aktion")
    if remaining is not None and remaining < cost:
        message = (
            f"Für {label} werden {cost} Tokens benötigt. "
            f"Dir stehen nur noch {remaining} Tokens zur Verfügung."
        )
    else:
        message = (
            f"Dein monatliches Token-Limit ist erreicht. "
            f"Verbraucht: {used} / {limit} Tokens. "
            f"Bitte wende dich an einen Administrator."
        )
    return {
        "error_code": "LIMIT_REACHED",
        "action_type": action_type,
        "cost": cost,
        "monthly_limit": limit,
        "used": used,
        "remaining": remaining,
        "message": message,
    }


async def reserve_action(
    db: AsyncSession,
    user: User,
    action_type: str,
    metadata: Optional[dict] = None,
):
    """Server-side quota enforcement.

    The expensive work (LLM / image generation) is only started after the
    quota for the action was atomically reserved; the charge always happens
    before any expensive work and can never be bypassed by the client. On
    failure the callee must call ``refund_reserved_usage``.
    """
    cost = await get_cost_for_action(db, action_type)
    try:
        return await spend_user_usage(db, user, action_type, cost, metadata)
    except LimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=build_limit_error(exc.action_type, exc.cost, exc.limit, exc.used),
        )