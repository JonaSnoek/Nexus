from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import AuditLog


async def log_action(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=ip_address,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
