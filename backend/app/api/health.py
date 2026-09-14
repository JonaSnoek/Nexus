from fastapi import APIRouter, Depends
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.system import HealthResponse
from app.providers.ollama import OllamaProvider
from app.models.user import User
from app.services.settings_service import sso_enabled

router = APIRouter(prefix="/api", tags=["health"])
provider = OllamaProvider()


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    setup_required = False
    try:
        await db.execute(text("SELECT 1"))
        result = await db.execute(select(func.count(User.id)))
        user_count = result.scalar()
        setup_required = user_count == 0
    except Exception:
        db_status = "error"

    result = await provider.healthcheck()
    ollama_status = result["status"]

    try:
        oidc_on = await sso_enabled(db)
    except Exception:
        oidc_on = False

    overall = "ok"
    if db_status != "ok" or ollama_status != "ok":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        ollama=ollama_status,
        setup_required=setup_required,
        oidc_enabled=oidc_on,
    )
