from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings as env_settings
from app.models.user import SystemSetting

# Keys used in the system_settings table. .env values are imported on first
# boot (bootstrap) and afterwards everything is managed via the admin panel.
SSO_KEYS = [
    "oidc_enabled",
    "oidc_issuer_url",
    "oidc_client_id",
    "oidc_client_secret",
    "oidc_redirect_uri",
    "oidc_group_admins",
    "oidc_group_users",
]
LIMIT_KEYS = [
    "default_token_limit",
    "default_message_limit",
    "chat_message_cost",
    "image_generation_cost",
]
IMAGE_KEYS = [
    "image_provider",
    "image_model",
    "image_api_url",
    "image_api_key",
]

# Action types charged against the monthly quota. The key is the internal
# action type (see API usage events), the value is the system_settings key
# holding the configured token cost of that action.
ACTION_COST_KEYS = {
    "CHAT_MESSAGE": "chat_message_cost",
    "IMAGE_GENERATION": "image_generation_cost",
}

DEFAULTS = {
    "oidc_enabled": "false",
    "oidc_issuer_url": "",
    "oidc_client_id": "",
    "oidc_client_secret": "",
    "oidc_redirect_uri": "",
    "oidc_group_admins": env_settings.OIDC_GROUP_ADMINS,
    "oidc_group_users": env_settings.OIDC_GROUP_USERS,
    "default_token_limit": "100",
    "default_message_limit": "1000",
    "chat_message_cost": "1",
    "image_generation_cost": "10",
    "image_provider": env_settings.IMAGE_PROVIDER or "none",
    "image_model": env_settings.IMAGE_MODEL or "",
    "image_api_url": env_settings.IMAGE_API_URL or "",
    "image_api_key": env_settings.IMAGE_API_KEY or "",
}


def _bool_value(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _int_value(value: Optional[str], fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


async def get_setting(db: AsyncSession, key: str, default: Optional[str] = None) -> Optional[str]:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting is not None and setting.value is not None:
        return setting.value
    return default


async def set_setting(db: AsyncSession, key: str, value: Optional[str]) -> None:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SystemSetting(key=key, value=value))
    await db.commit()


async def bootstrap_settings(db: AsyncSession) -> None:
    """Import .env OIDC/bootstrap values into the settings table once."""
    for key, fallback in DEFAULTS.items():
        existing = await get_setting(db, key)
        if existing is not None:
            continue
        value = fallback
        if key == "oidc_enabled":
            value = str(bool(env_settings.OIDC_ENABLED)).lower()
        elif key == "oidc_issuer_url":
            value = env_settings.OIDC_ISSUER_URL
        elif key == "oidc_client_id":
            value = env_settings.OIDC_CLIENT_ID
        elif key == "oidc_client_secret":
            value = env_settings.OIDC_CLIENT_SECRET
        elif key == "oidc_redirect_uri":
            value = env_settings.OIDC_REDIRECT_URI
        elif key == "image_provider":
            value = env_settings.IMAGE_PROVIDER or "none"
        elif key == "image_model":
            value = env_settings.IMAGE_MODEL
        elif key == "image_api_url":
            value = env_settings.IMAGE_API_URL
        elif key == "image_api_key":
            value = env_settings.IMAGE_API_KEY
        await set_setting(db, key, value)


async def sso_enabled(db: AsyncSession) -> bool:
    value = await get_setting(db, "oidc_enabled", "false")
    return _bool_value(value or "false")


async def get_sso_settings(db: AsyncSession) -> dict:
    return {
        "oidc_enabled": _bool_value(await get_setting(db, "oidc_enabled", "false") or "false"),
        "oidc_issuer_url": await get_setting(db, "oidc_issuer_url", "") or "",
        "oidc_client_id": await get_setting(db, "oidc_client_id", "") or "",
        "oidc_client_secret": await get_setting(db, "oidc_client_secret", "") or "",
        "oidc_redirect_uri": await get_setting(db, "oidc_redirect_uri", "") or "",
        "oidc_group_admins": await get_setting(db, "oidc_group_admins", DEFAULTS["oidc_group_admins"]),
        "oidc_group_users": await get_setting(db, "oidc_group_users", DEFAULTS["oidc_group_users"]),
    }


async def get_default_limits(db: AsyncSession) -> dict:
    return {
        "default_token_limit": _int_value(
            await get_setting(db, "default_token_limit", DEFAULTS["default_token_limit"]),
            _int_value(DEFAULTS["default_token_limit"], 100),
        ),
        "default_message_limit": _int_value(
            await get_setting(db, "default_message_limit", DEFAULTS["default_message_limit"]),
            _int_value(DEFAULTS["default_message_limit"], 1000),
        ),
    }


async def get_action_costs(db: AsyncSession) -> dict:
    """Configured NEXUS quota cost per action type.

    1 token quota = 1 internal NEXUS consumption unit. The values are the ones
    deducted from the monthly quota; they do NOT need to equal the token
    counters reported by the LLM provider.
    """
    return {
        "chat_message_cost": _int_value(
            await get_setting(db, "chat_message_cost", DEFAULTS["chat_message_cost"]),
            _int_value(DEFAULTS["chat_message_cost"], 1),
        ),
        "image_generation_cost": _int_value(
            await get_setting(db, "image_generation_cost", DEFAULTS["image_generation_cost"]),
            _int_value(DEFAULTS["image_generation_cost"], 10),
        ),
    }


async def get_cost_for_action(db: AsyncSession, action_type: str) -> int:
    key = ACTION_COST_KEYS.get(action_type)
    if key is None:
        return 1
    return (await get_action_costs(db)).get(key, 1)


async def get_limits_config(db: AsyncSession) -> dict:
    """Complete limits + consumption configuration for the admin panel."""
    limits = await get_default_limits(db)
    costs = await get_action_costs(db)
    return {**limits, **costs}


async def apply_sso_update(db: AsyncSession, body: dict) -> dict:
    updates = {
        "oidc_enabled": "true" if body.get("oidc_enabled") is True else "false" if body.get("oidc_enabled") is False else None,
        "oidc_issuer_url": body.get("oidc_issuer_url"),
        "oidc_client_id": body.get("oidc_client_id"),
        "oidc_client_secret": body.get("oidc_client_secret"),
        "oidc_redirect_uri": body.get("oidc_redirect_uri"),
        "oidc_group_admins": body.get("oidc_group_admins"),
        "oidc_group_users": body.get("oidc_group_users"),
    }
    for key, value in updates.items():
        if value is not None:
            await set_setting(db, key, str(value))
    return await get_sso_settings(db)


async def apply_limits_update(db: AsyncSession, body: dict) -> dict:
    if body.get("default_token_limit") is not None:
        await set_setting(db, "default_token_limit", str(body["default_token_limit"]))
    if body.get("default_message_limit") is not None:
        await set_setting(db, "default_message_limit", str(body["default_message_limit"]))
    if body.get("chat_message_cost") is not None:
        await set_setting(db, "chat_message_cost", str(body["chat_message_cost"]))
    if body.get("image_generation_cost") is not None:
        await set_setting(db, "image_generation_cost", str(body["image_generation_cost"]))
    return await get_limits_config(db)


# ---------------------------------------------------------------------------
# Image generation provider configuration
# ---------------------------------------------------------------------------

def _normalize_provider_name(value: Optional[str]) -> str:
    value = (value or "").strip().lower()
    return value if value in ("none", "openai_compatible") else "none"


async def get_image_provider_settings(db: AsyncSession) -> dict:
    """Public (safe) provider settings - never returns the raw API key.

    Only a boolean ``has_api_key`` and a masked tail are exposed so the
    values can never leak to the frontend.
    """
    provider = _normalize_provider_name(await get_setting(db, "image_provider", DEFAULTS["image_provider"]))
    model = (await get_setting(db, "image_model", DEFAULTS["image_model"]) or DEFAULTS["image_model"]) or ""
    api_url = (await get_setting(db, "image_api_url", DEFAULTS["image_api_url"]) or DEFAULTS["image_api_url"]) or ""
    api_key = (await get_setting(db, "image_api_key", DEFAULTS["image_api_key"]) or "") or ""

    tail = ""
    if api_key:
        tail = api_key[-4:] if len(api_key) >= 4 else "****"
    return {
        "image_provider": provider,
        "image_model": model,
        "image_api_url": api_url,
        "has_api_key": bool(api_key),
        "api_key_tail": tail,
        "configured": provider == "openai_compatible" and bool(api_url.strip()),
    }


async def get_image_provider_config(db: AsyncSession) -> dict:
    """Full internal provider config (may contain the API key - backend only)."""
    public = await get_image_provider_settings(db)
    api_key = (await get_setting(db, "image_api_key", DEFAULTS["image_api_key"]) or "") or ""
    return {
        "image_provider": public["image_provider"],
        "image_model": public["image_model"],
        "image_api_url": public["image_api_url"],
        "image_api_key": api_key,
        "configured": public["configured"],
    }


async def apply_image_provider_update(db: AsyncSession, body: dict) -> dict:
    if body.get("image_provider") is not None:
        await set_setting(db, "image_provider", _normalize_provider_name(body["image_provider"]))
    if body.get("image_model") is not None:
        value = str(body["image_model"] or "").strip()
        await set_setting(db, "image_model", value)
    if body.get("image_api_url") is not None:
        value = str(body["image_api_url"] or "").strip()
        await set_setting(db, "image_api_url", value)
    if "image_api_key" in body:
        value = body["image_api_key"]
        # Empty string clears the key; None keeps the existing one.
        if value is not None:
            stripped = str(value).strip()
            await set_setting(db, "image_api_key", stripped if stripped else None)
    return await get_image_provider_settings(db)