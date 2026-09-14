"""User management endpoint tests (admin-only routes)."""

from app.models.user import Permission
from app.services.user_service import check_permission

CREATE_BODY = {
    "username": "alice",
    "password": "alice-password",
    "email": "alice@test.local",
    "display_name": "Alice",
    "role": "USER",
}


async def test_list_users_admin(client, admin_headers):
    response = await client.get("/api/users/", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    usernames = [u["username"] for u in data["users"]]
    assert "admin" in usernames


async def test_list_users_regular_user_forbidden(client, user_headers):
    response = await client.get("/api/users/", headers=user_headers)
    assert response.status_code == 403


async def test_create_user(client, admin_headers):
    response = await client.post("/api/users/", headers=admin_headers, json=CREATE_BODY)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "alice"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert data["is_sso"] is False

    # Duplicate usernames are rejected.
    duplicate = await client.post("/api/users/", headers=admin_headers, json=CREATE_BODY)
    assert duplicate.status_code == 400


async def test_create_user_regular_user_forbidden(client, user_headers):
    response = await client.post("/api/users/", headers=user_headers, json=CREATE_BODY)
    assert response.status_code == 403


async def test_update_user(client, admin_headers, regular_user):
    response = await client.put(
        f"/api/users/{regular_user.id}",
        headers=admin_headers,
        json={"display_name": "Renamed User", "email": "renamed@test.local"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Renamed User"
    assert data["email"] == "renamed@test.local"


async def test_update_user_not_found(client, admin_headers):
    response = await client.put(
        "/api/users/99999", headers=admin_headers, json={"display_name": "X"}
    )
    assert response.status_code == 404


async def test_deactivate_user(client, admin_headers, regular_user):
    response = await client.delete(
        f"/api/users/{regular_user.id}", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["detail"] == "User deactivated"

    # A deactivated user can no longer authenticate.
    login = await client.post(
        "/api/auth/login", json={"username": "user1", "password": "password123"}
    )
    assert login.status_code == 403


async def test_deactivate_self_forbidden(client, admin_headers, admin_user):
    response = await client.delete(f"/api/users/{admin_user.id}", headers=admin_headers)
    assert response.status_code == 400


async def test_update_permissions(client, admin_headers, db_session, regular_user):
    permission = Permission(name="chat.use", description="Can use chat")
    db_session.add(permission)
    await db_session.commit()
    await db_session.refresh(permission)

    response = await client.put(
        f"/api/users/{regular_user.id}/permissions",
        headers=admin_headers,
        json={"permission_ids": [permission.id]},
    )
    assert response.status_code == 200
    assert response.json()["detail"] == "Permissions updated"

    assert await check_permission(db_session, regular_user.id, "chat.use") is True


async def test_update_permissions_regular_user_forbidden(
    client, user_headers, regular_user
):
    response = await client.put(
        f"/api/users/{regular_user.id}/permissions",
        headers=user_headers,
        json={"permission_ids": []},
    )
    assert response.status_code == 403


async def test_update_limits(client, admin_headers, regular_user):
    response = await client.put(
        f"/api/users/{regular_user.id}/limits",
        headers=admin_headers,
        json={"daily_token_limit": 2000, "daily_message_limit": 25},
    )
    assert response.status_code == 200

    detail = await client.get(f"/api/users/{regular_user.id}", headers=admin_headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["daily_token_limit"] == 2000
    assert data["daily_message_limit"] == 25