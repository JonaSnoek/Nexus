"""Shared pytest fixtures and configuration for the NEXUS test suite.

This file is a copy of ``tests/conftest.py`` adapted for the ``backend/``
directory: the backend package root is the *parent* of this file, and the test
database lives under a backend-specific name so it never collides with the
root-level test run.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Make the backend package importable.
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# Force test configuration before importing any application module.
# ---------------------------------------------------------------------------
TEST_DB_PATH = Path(tempfile.gettempdir()) / "nexus_test_backend.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"] = "test-secret-key-for-nexus"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["OLLAMA_URL"] = "http://ollama.test:11434"
os.environ["FIRST_ADMIN_USERNAME"] = ""
os.environ["FIRST_ADMIN_PASSWORD"] = ""
os.environ["FIRST_ADMIN_EMAIL"] = ""

# ---------------------------------------------------------------------------
# Application imports (safe now that the environment is configured).
# ---------------------------------------------------------------------------
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.database import Base, get_db  # noqa: E402
from app.providers.ollama import OllamaProvider  # noqa: E402
from app.services.user_service import create_user  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


def _session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_engine():
    """A fresh SQLite database, dropped/created per test for full isolation."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except OSError:
            pass


@pytest_asyncio.fixture
async def db_session(db_engine):
    """A direct async session bound to the per-test database engine."""
    factory = _session_factory(db_engine)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """An httpx client mounted over the FastAPI app with the test database."""
    import httpx

    factory = _session_factory(db_engine)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
            finally:
                await session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=fastapi_app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=True,
        ) as c:
            yield c
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def regular_user(db_session):
    """A plain USER-role account used across the tests."""
    return await create_user(
        db_session,
        username="user1",
        password="password123",
        email="user1@test.local",
        display_name="Regular User",
        role="USER",
    )


@pytest_asyncio.fixture
async def admin_user(db_session):
    """An ADMIN-role account used across the tests."""
    return await create_user(
        db_session,
        username="admin",
        password="admin123",
        email="admin@test.local",
        display_name="Admin User",
        role="ADMIN",
    )


async def _login(client, username, password):
    response = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(client, regular_user):
    """Bearer auth header for the regular user."""
    return await _login(client, "user1", "password123")


@pytest_asyncio.fixture
async def admin_headers(client, admin_user):
    """Bearer auth header for the admin user."""
    return await _login(client, "admin", "admin123")


@pytest_asyncio.fixture(autouse=True)
async def mock_ollama(monkeypatch):
    """Replace every Ollama network call with deterministic fakes."""

    async def fake_chat_stream(self, messages, model=None, **kwargs):
        for token in ("Hello", " from", " NEXUS"):
            yield token

    async def fake_generate(self, prompt, model=None, **kwargs):
        return "Generated response"

    async def fake_healthcheck(self):
        return {"status": "ok", "details": {"models": []}}

    async def fake_list_models(self):
        return [
            {
                "name": "qwen3:8b",
                "size": 4700000000,
                "digest": "abcd1234",
                "modified_at": "2024-01-01T00:00:00",
            }
        ]

    async def fake_pull_model(self, model_name):
        return True

    async def fake_get_model_info(self, model_name):
        return {"name": model_name}

    fakes = {
        "chat_stream": fake_chat_stream,
        "generate": fake_generate,
        "healthcheck": fake_healthcheck,
        "list_models": fake_list_models,
        "pull_model": fake_pull_model,
        "get_model_info": fake_get_model_info,
    }
    for name, impl in fakes.items():
        monkeypatch.setattr(OllamaProvider, name, impl)
    yield


@pytest_asyncio.fixture
async def auth_headers(client, admin_user, regular_user):
    """Convenience fixture returning both auth header sets."""
    admin = await _login(client, "admin", "admin123")
    user = await _login(client, "user1", "password123")
    return {"admin": admin, "user": user}