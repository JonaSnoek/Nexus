"""Health and setup-status endpoint tests."""

from app.providers.ollama import OllamaProvider


async def test_health_endpoint(client):
    # Health requires no authentication.
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["ollama"] == "ok"


async def test_health_with_db(client, monkeypatch):
    """Database remains 'ok' and the overall status degrades when Ollama is down."""

    async def broken_healthcheck(self):
        return {"status": "error", "details": "connection refused"}

    monkeypatch.setattr(OllamaProvider, "healthcheck", broken_healthcheck)

    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "ok"
    assert data["ollama"] == "error"
    assert data["status"] == "degraded"


async def test_setup_status(client):
    # No users exist on a fresh test database, so setup is required.
    response = await client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["needs_setup"] is True
    assert data["first_admin_configured"] is False


async def test_setup_status_after_user_exists(client, regular_user):
    # Once a user exists, setup is no longer needed.
    response = await client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["needs_setup"] is False