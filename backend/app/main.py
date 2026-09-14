import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import init_db
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.chat import router as chat_router
from app.api.admin import router as admin_router
from app.api.health import router as health_router
from app.api.permissions import router as permissions_router
from app.api.setup import router as setup_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    from sqlalchemy import select
    from app.core.database import async_session
    from app.models.user import User

    if settings.FIRST_ADMIN_USERNAME and settings.FIRST_ADMIN_PASSWORD:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.username == settings.FIRST_ADMIN_USERNAME))
            existing = result.scalar_one_or_none()
            if existing is None:
                from app.core.security import get_password_hash
                admin = User(
                    username=settings.FIRST_ADMIN_USERNAME,
                    hashed_password=get_password_hash(settings.FIRST_ADMIN_PASSWORD),
                    email=settings.FIRST_ADMIN_EMAIL or None,
                    display_name=settings.FIRST_ADMIN_USERNAME,
                    role="ADMIN",
                )
                session.add(admin)
                await session.commit()

    yield


app = FastAPI(title="NEXUS API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(health_router)
app.include_router(permissions_router)
app.include_router(setup_router)


@app.get("/")
async def root():
    return {"app": "NEXUS", "status": "running", "version": "1.0.0"}


static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")