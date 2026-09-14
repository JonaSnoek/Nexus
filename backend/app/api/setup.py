from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.auth import SetupRequest
from app.services.user_service import create_user
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()
    needs_setup = user_count == 0
    return {
        "needs_setup": needs_setup,
        "first_admin_configured": bool(settings.FIRST_ADMIN_USERNAME),
    }


@router.post("/")
async def perform_setup(body: SetupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()
    if user_count and user_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setup already completed")

    user = await create_user(
        db,
        username=body.username,
        password=body.password,
        email=body.email,
        display_name=body.display_name,
        role="ADMIN",
    )
    await log_action(db, "setup_completed", user_id=user.id, details=f"Initial setup by {body.username}")
    return {"detail": "Setup completed", "user": user.username}