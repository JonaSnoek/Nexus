from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User, UserRole, Permission
from app.schemas.user import PermissionResponse

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


@router.get("/", response_model=list[PermissionResponse])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Permission).order_by(Permission.id))
    return result.scalars().all()


@router.post("/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_permission(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    name = body.get("name", "")
    description = body.get("description", "")
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission name required")

    result = await db.execute(select(Permission).where(Permission.name == name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission already exists")

    perm = Permission(name=name, description=description)
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm