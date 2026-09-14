import pytest

from app.core.database import async_session
from app.models.user import User
from app.services.settings_service import get_default_limits
from sqlalchemy import select


async def test_default_limits_endpoint(client, admin_headers):
    response = await client.get("/api/admin/settings/limits", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "default_token_limit" in data
    assert "default_message_limit" in data
    assert "chat_message_cost" in data
    assert "image_generation_cost" in data
    assert data["default_token_limit"] == 100
    assert data["default_message_limit"] == 1000
    assert data["chat_message_cost"] == 1
    assert data["image_generation_cost"] == 10


async def test_update_default_limits(client, admin_headers, db_session):
    response = await client.put(
        "/api/admin/settings/limits",
        headers=admin_headers,
        json={"default_token_limit": 50000, "default_message_limit": 250},
    )
    assert response.status_code == 200
    assert response.json()["default_token_limit"] == 50000
    assert response.json()["default_message_limit"] == 250

    stored = await get_default_limits(db_session)
    assert stored["default_token_limit"] == 50000
    assert stored["default_message_limit"] == 250


async def test_default_limits_forbidden_for_user(client, user_headers):
    response = await client.get("/api/admin/settings/limits", headers=user_headers)
    assert response.status_code == 403


async def test_sso_settings_roundtrip(client, admin_headers):
    response = await client.get("/api/admin/settings/sso", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["oidc_enabled"] is False

    update = await client.put(
        "/api/admin/settings/sso",
        headers=admin_headers,
        json={
            "oidc_enabled": True,
            "oidc_issuer_url": "https://auth.example.test/application/o/nexus/",
            "oidc_client_id": "nexus",
            "oidc_client_secret": "topsecret",
            "oidc_redirect_uri": "http://localhost/auth/callback",
            "oidc_group_admins": "admins",
            "oidc_group_users": "users",
        },
    )
    assert update.status_code == 200
    assert update.json()["oidc_enabled"] is True

    policy_enabled = await client.put(
        "/api/admin/settings/sso",
        headers=admin_headers,
        json={"oidc_enabled": False},
    )
    assert policy_enabled.status_code == 200
    assert policy_enabled.json()["oidc_enabled"] is False


async def test_create_user_uses_default_limits(client, admin_headers, db_session):
    to_lower = 777
    await client.put(
        "/api/admin/settings/limits",
        headers=admin_headers,
        json={"default_token_limit": to_lower, "default_message_limit": 33},
    )

    response = await client.post(
        "/api/users/",
        headers=admin_headers,
        json={
            "username": "newfromdefaults",
            "password": "password123",
            "role": "user",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["monthly_token_limit"] == 777
    assert data["monthly_message_limit"] == 33

    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "newfromdefaults"))
        user = result.scalar_one()
        assert (user.monthly_token_limit, user.monthly_message_limit) == (777, 33)


async def test_create_user_with_explicit_limits(client, admin_headers):
    response = await client.post(
        "/api/users/",
        headers=admin_headers,
        json={
            "username": "explicitlimits",
            "password": "password123",
            "role": "user",
            "monthly_token_limit": 1234,
            "monthly_message_limit": 5,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["monthly_token_limit"] == 1234
    assert data["monthly_message_limit"] == 5


async def test_me_includes_monthly_usage(client, user_headers):
    response = await client.get("/api/auth/me", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "period" in data
    assert "monthly_token_limit" in data
    assert "monthly_message_limit" in data
    assert "tokens_used_month" in data
    assert "tokens_remaining_month" in data
    assert "messages_used_month" in data
    assert "messages_remaining_month" in data
    assert data["tokens_remaining_month"] >= 0


async def test_user_usage_uses_period(client, admin_headers, regular_user):
    response = await client.get(
        f"/api/users/{regular_user.id}/usage", headers=admin_headers
    )
    assert response.status_code == 200
    records = response.json()
    assert isinstance(records, list)
    for record in records:
        assert "period" in record
        assert "tokens_used" in record
        assert "messages_used" in record