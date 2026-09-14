"""Auth endpoint tests: login, setup, /me, and token expiry."""

from datetime import timedelta

from app.core.security import create_access_token

SETUP_BODY = {
    "username": "setup_admin",
    "password": "setup-password-123",
    "email": "setup@test.local",
    "display_name": "Setup Admin",
}


async def test_setup_creates_admin(client):
    response = await client.post("/api/auth/setup", json=SETUP_BODY)
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"

    # A second setup attempt must be refused now that a user exists.
    second = await client.post(
        "/api/auth/setup",
        json={
            "username": "second_admin",
            "password": "setup-password-123",
            "email": "second@test.local",
            "display_name": "Second Admin",
        },
    )
    assert second.status_code == 400


async def test_login_success(client, admin_user):
    response = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client, admin_user):
    response = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "not-the-password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_nonexistent_user(client):
    response = await client.post(
        "/api/auth/login", json={"username": "ghost", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_disabled_user(client, db_session):
    from app.services.user_service import get_user_by_username

    await get_user_by_username(db_session, "ghost")
    # Create + disable a user to verify the "account disabled" path.
    from app.services.user_service import create_user

    user = await create_user(
        db_session,
        username="disabled",
        password="password123",
        email="disabled@test.local",
        role="USER",
    )
    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/auth/login", json={"username": "disabled", "password": "password123"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Account disabled"


async def test_get_me_authenticated(client, user_headers):
    response = await client.get("/api/auth/me", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "user1"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert data["is_sso"] is False


async def test_get_me_unauthenticated(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_get_me_invalid_token(client):
    response = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_token_expiration(client, admin_user):
    expired_token = create_access_token(
        {"sub": str(admin_user.id)}, expires_delta=timedelta(seconds=-10)
    )
    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


async def test_setup_status_no_admin(client):
    response = await client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["needs_setup"] is True
    assert data["first_admin_configured"] is False