"""Permission checking and listing tests."""

from app.models.user import Permission, UserPermission
from app.services.user_service import check_permission


async def test_permission_check_allowed(db_session, regular_user):
    permission = Permission(name="chat.use", description="Use chat")
    db_session.add(permission)
    await db_session.commit()
    await db_session.refresh(permission)

    db_session.add(UserPermission(user_id=regular_user.id, permission_id=permission.id))
    await db_session.commit()

    assert await check_permission(db_session, regular_user.id, "chat.use") is True
    # Other permission not assigned must be denied.
    assert await check_permission(db_session, regular_user.id, "image.generate") is False


async def test_permission_check_denied(db_session, regular_user):
    # No permissions assigned — everything denied.
    assert await check_permission(db_session, regular_user.id, "chat.use") is False
    assert await check_permission(db_session, regular_user.id, "admin.access") is False


async def test_admin_has_all_permissions(db_session, admin_user):
    # Admins bypass permission checks.
    assert await check_permission(db_session, admin_user.id, "chat.use") is True
    assert await check_permission(db_session, admin_user.id, "image.generate") is True
    assert await check_permission(db_session, admin_user.id, "any.permission") is True


async def test_list_permissions(client, user_headers, db_session):
    # Seed four permissions.
    for name, description in [
        ("chat.use", "Use chat"),
        ("chat.manage", "Manage chats"),
        ("image.generate", "Generate images"),
        ("admin.access", "Access admin panel"),
    ]:
        db_session.add(Permission(name=name, description=description))
    await db_session.commit()

    response = await client.get("/api/permissions/", headers=user_headers)
    assert response.status_code == 200
    body = response.json()
    names = {p["name"] for p in body}
    assert {"chat.use", "chat.manage", "image.generate", "admin.access"}.issubset(names)


async def test_create_permission(client, admin_headers, db_session):
    response = await client.post(
        "/api/permissions/",
        headers=admin_headers,
        json={"name": "image.generate", "description": "Generate images"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "image.generate"
    assert data["description"] == "Generate images"


async def test_create_permission_duplicate(client, admin_headers, db_session):
    # Seed an existing permission.
    db_session.add(Permission(name="chat.use", description="Use chat"))
    await db_session.commit()

    response = await client.post(
        "/api/permissions/",
        headers=admin_headers,
        json={"name": "chat.use", "description": "Use chat"},
    )
    assert response.status_code == 400


async def test_create_permission_regular_user_forbidden(client, user_headers):
    response = await client.post(
        "/api/permissions/",
        headers=user_headers,
        json={"name": "test.perm", "description": "test"},
    )
    assert response.status_code == 403