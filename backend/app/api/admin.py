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
from app.models.user import User, UserRole, AuditLog, Chat, Message
from app.schemas.system import (
    SystemInfoResponse,
    SsoSettingsResponse,
    SsoSettingsUpdate,
    DefaultLimitsResponse,
    DefaultLimitsUpdate,
)
from app.providers.ollama import OllamaProvider
from app.services.settings_service import (
    get_sso_settings,
    apply_sso_update,
    get_default_limits,
    apply_limits_update,
)
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


@router.get("/settings/limits", response_model=DefaultLimitsResponse)
async def get_limit_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return await get_default_limits(db)


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