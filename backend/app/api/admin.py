import os
import platform
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User, UserRole, AuditLog, Chat, Message, Usage, UsageEvent
from app.schemas.system import (
    SystemInfoResponse,
    SsoSettingsResponse,
    SsoSettingsUpdate,
    DefaultLimitsResponse,
    DefaultLimitsUpdate,
)
from app.schemas.image import ImageProviderSettingsResponse, ImageProviderSettingsUpdate
from app.schemas.user import UserLimitsResponse
from app.providers.ollama import OllamaProvider
from app.services.settings_service import (
    get_sso_settings,
    apply_sso_update,
    get_limits_config,
    apply_limits_update,
    get_image_provider_settings,
    apply_image_provider_update,
)
from app.services.user_service import get_user_by_id, usage_view_for_user, CURRENT_PERIOD
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/admin", tags=["admin"])
provider = OllamaProvider()


def _get_cpu_percent() -> Optional[float]:
    try:
        os_name = platform.system()
        if os_name == "Linux":
            with open("/proc/loadavg", "r") as f:
                parts = f.read().split()
                load1 = float(parts[0])
                with open("/proc/cpuinfo") as cf:
                    cores = sum(1 for line in cf if line.startswith("processor"))
                return round(load1 / max(cores, 1) * 100.0, 2)
        elif os_name == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", ctypes.c_uint), ("dwHighDateTime", ctypes.c_uint)]
            idle_time, kernel_time, user_time = FILETIME(), FILETIME(), FILETIME()
            kernel32.GetSystemTimes(ctypes.byref(idle_time), ctypes.byref(kernel_time), ctypes.byref(user_time))
            return None
        return None
    except Exception:
        return None


def _get_memory_info() -> tuple:
    try:
        os_name = platform.system()
        if os_name == "Linux":
            with open("/proc/meminfo", "r") as f:
                lines = {}
                for line in f:
                    if ":" in line:
                        key, rest = line.split(":", 1)
                        lines[key] = int(rest.strip().split()[0]) * 1024
            total = lines.get("MemTotal", 0)
            available = lines.get("MemAvailable", 0)
            used = total - available
            percent = round(used / total * 100.0, 2) if total else 0.0
            return total, used, percent
        elif os_name == "Windows":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys, m.ullTotalPhys - m.ullAvailPhys, float(m.dwMemoryLoad)
        return None, None, None
    except Exception:
        return None, None, None


def _get_disk_info() -> tuple:
    try:
        os_name = platform.system()
        if os_name == "Windows":
            total = ctypes = None
            import shutil
            usage = shutil.disk_usage("C:\\")
            return usage.total, usage.used, round(usage.used / usage.total * 100.0, 2) if usage.total else 0.0
        elif os_name == "Linux":
            with open("/proc/mounts") as f:
                pass
            import shutil
            usage = shutil.disk_usage("/")
            return usage.total, usage.used, round(usage.used / usage.total * 100.0, 2) if usage.total else 0.0
        return None, None, None
    except Exception:
        return None, None, None


def _get_uptime() -> Optional[float]:
    try:
        os_name = platform.system()
        if os_name == "Linux":
            with open("/proc/uptime", "r") as f:
                return float(f.read().split()[0])
        return None
    except Exception:
        return None


@router.get("/dashboard")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    active_user_count = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar()
    chat_count = (await db.execute(select(func.count(Chat.id)))).scalar()
    message_count = (await db.execute(select(func.count(Message.id)))).scalar()
    total_tokens = (await db.execute(
        select(func.coalesce(func.sum(Message.tokens), 0))
    )).scalar()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_tokens_today = (await db.execute(
        select(func.coalesce(func.sum(Message.tokens), 0)).where(
            Message.created_at >= today_start
        )
    )).scalar()
    messages_today = (await db.execute(
        select(func.count(Message.id)).where(Message.created_at >= today_start)
    )).scalar()

    return {
        "users": user_count,
        "active_users": active_user_count,
        "chats": chat_count,
        "messages": message_count,
        "messages_today": messages_today,
        "tokens_today": total_tokens_today,
        "total_tokens": total_tokens,
        "date": today,
    }


@router.get("/logs")
async def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    query = select(AuditLog, User.username).join(User, User.id == AuditLog.user_id, isouter=True)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    rows = result.all()
    return {
        "logs": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "username": username or "system",
                "action": l.action,
                "resource": None,
                "details": l.details,
                "ip_address": l.ip_address,
                "created_at": l.created_at,
            }
            for l, username in rows
        ],
        "total": len(rows),
    }


@router.get("/system", response_model=SystemInfoResponse)
async def get_system_info(current_user: User = Depends(get_current_active_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    cpu = _get_cpu_percent()
    mem_total, mem_used, mem_percent = _get_memory_info()
    disk_total, disk_used, disk_percent = _get_disk_info()
    uptime = _get_uptime()

    return SystemInfoResponse(
        cpu_percent=cpu,
        memory_total=mem_total,
        memory_used=mem_used,
        memory_percent=mem_percent,
        disk_total=disk_total,
        disk_used=disk_used,
        disk_percent=disk_percent,
        uptime=uptime,
    )


@router.get("/models")
async def list_ollama_models(current_user: User = Depends(get_current_active_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    try:
        models = await provider.list_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama unavailable: {str(e)}")


@router.post("/models/pull")
async def pull_ollama_model(
    body: dict,
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    model_name = body.get("model", "")
    if not model_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name required")
    success = await provider.pull_model(model_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to pull model")
    return {"detail": f"Model {model_name} pulled successfully"}


@router.get("/models/status")
async def model_status(current_user: User = Depends(get_current_active_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    try:
        health = await provider.healthcheck()
        models = await provider.list_models()
        default_present = any(m["name"].startswith(settings.NEXUS_LLM_MODEL.split(":")[0]) for m in models)
        return {
            "ollama": health["status"],
            "default_model": settings.NEXUS_LLM_MODEL,
            "default_model_present": default_present,
            "model_count": len(models),
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama unavailable: {str(e)}")


@router.get("/settings/sso", response_model=SsoSettingsResponse)
async def get_sso_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return await get_sso_settings(db)


@router.put("/settings/sso", response_model=SsoSettingsResponse)
async def update_sso_config(
    body: SsoSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await apply_sso_update(db, body.model_dump(exclude_unset=True))
    await log_action(db, "sso_settings_updated", user_id=current_user.id, details="SSO/OIDC settings updated")
    return result


@router.get("/settings/images", response_model=ImageProviderSettingsResponse)
async def get_image_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return await get_image_provider_settings(db)


@router.put("/settings/images", response_model=ImageProviderSettingsResponse)
async def update_image_config(
    body: ImageProviderSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await apply_image_provider_update(db, body.model_dump(exclude_unset=True))
    await log_action(db, "image_settings_updated", user_id=current_user.id, details="Image provider settings updated")
    return result


@router.get("/settings/limits", response_model=DefaultLimitsResponse)
async def get_limit_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return await get_limits_config(db)


@router.put("/settings/limits", response_model=DefaultLimitsResponse)
async def update_limit_config(
    body: DefaultLimitsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await apply_limits_update(db, body.model_dump(exclude_unset=True))
    await log_action(db, "limits_settings_updated", user_id=current_user.id, details="Default limits updated")
    return result


@router.get("/users/{user_id}/limits", response_model=UserLimitsResponse)
async def get_user_limits_config(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Admin view of one user's limit state plus current-period usage."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    view = await usage_view_for_user(db, user)
    return UserLimitsResponse(
        user_id=user.id,
        limits_exempt=bool(user.limits_exempt),
        custom_monthly_token_limit=user.custom_monthly_token_limit,
        unlimited=bool(user.unlimited),
        effective_token_limit=view["effective_token_limit"],
        has_token_limit=view["has_token_limit"],
        tokens_used=view["tokens_used_month"],
        tokens_remaining=view["tokens_remaining"],
        used_percent=view["used_percent"],
        monthly_message_limit=user.monthly_message_limit,
        messages_used=view["messages_used_month"],
    )


@router.get("/usage/summary")
async def get_usage_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Per-user quota summary for the current period (admin statistics)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    period = CURRENT_PERIOD()
    result = await db.execute(
        select(
            User.id, User.username, User.display_name, User.role,
            User.limits_exempt, User.unlimited, User.custom_monthly_token_limit,
            Usage.tokens_used, Usage.messages_used,
        )
        .join(Usage, Usage.user_id == User.id)
        .where(Usage.period == period)
        .order_by(Usage.tokens_used.desc())
    )
    rows = result.all()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_counts = {}
    today_result = await db.execute(
        select(
            UsageEvent.user_id,
            func.sum(UsageEvent.tokens),
            func.count(UsageEvent.id),
        )
        .where(UsageEvent.created_at >= today_start, UsageEvent.period == period)
        .group_by(UsageEvent.user_id)
    )
    for user_id, event_tokens, event_count in today_result.all():
        today_counts[user_id] = {"tokens_today": event_tokens or 0, "actions_today": event_count or 0}

    action_counts = {}
    action_result = await db.execute(
        select(UsageEvent.user_id, UsageEvent.action_type, func.count(UsageEvent.id))
        .where(UsageEvent.period == period)
        .group_by(UsageEvent.user_id, UsageEvent.action_type)
    )
    for user_id, action_type, count in action_result.all():
        action_counts.setdefault(user_id, {})[action_type] = count

    defaults = await get_limits_config(db)
    default_token_limit = defaults["default_token_limit"]

    users = []
    for (
        uid, username, display_name, role, exempt, unlimited, custom, tokens_used, messages_used
    ) in rows:
        if unlimited:
            effective = None
        elif exempt:
            effective = custom
        else:
            effective = default_token_limit
        has_limit = effective is not None
        remaining = max(effective - tokens_used, 0) if has_limit else None
        users.append({
            "user_id": uid,
            "username": username,
            "display_name": display_name,
            "role": role.value.lower() if isinstance(role, UserRole) else str(role).lower(),
            "limit": effective,
            "unlimited": bool(unlimited),
            "has_limit": has_limit,
            "used": tokens_used,
            "messages": messages_used,
            "remaining": remaining,
            "used_percent": round(tokens_used / effective * 100) if has_limit and effective > 0 else (100 if has_limit and tokens_used else None),
            **today_counts.get(uid, {"tokens_today": 0, "actions_today": 0}),
            "actions": action_counts.get(uid, {}),
        })

    total_tokens = (await db.execute(
        select(func.coalesce(func.sum(Usage.tokens_used), 0)).where(Usage.period == period)
    )).scalar()
    total_messages = (await db.execute(
        select(func.coalesce(func.sum(Usage.messages_used), 0)).where(Usage.period == period)
    )).scalar()
    total_actions = (await db.execute(
        select(func.count(UsageEvent.id)).where(UsageEvent.period == period)
    )).scalar()

    # Breakdown by action type (only counts events that survive refunds).
    total_chat_tokens = (await db.execute(
        select(func.coalesce(func.sum(UsageEvent.tokens), 0))
        .where(UsageEvent.period == period, UsageEvent.action_type == "CHAT_MESSAGE")
    )).scalar()
    total_image_tokens = (await db.execute(
        select(func.coalesce(func.sum(UsageEvent.tokens), 0))
        .where(UsageEvent.period == period, UsageEvent.action_type == "IMAGE_GENERATION")
    )).scalar()
    total_chat_actions = (await db.execute(
        select(func.count(UsageEvent.id))
        .where(UsageEvent.period == period, UsageEvent.action_type == "CHAT_MESSAGE")
    )).scalar()
    total_image_actions = (await db.execute(
        select(func.count(UsageEvent.id))
        .where(UsageEvent.period == period, UsageEvent.action_type == "IMAGE_GENERATION")
    )).scalar()

    return {
        "period": period,
        "users": users,
        "total_tokens_used": total_tokens,
        "total_messages": total_messages,
        "total_actions": total_actions,
        "total_chat_tokens": total_chat_tokens,
        "total_image_tokens": total_image_tokens,
        "total_chat_actions": total_chat_actions,
        "total_image_actions": total_image_actions,
        "default_token_limit": default_token_limit,
    }