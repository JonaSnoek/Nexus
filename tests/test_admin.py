"""Admin endpoint tests: dashboard, audit logs, and system info."""

DASHBOARD_KEYS = (
    "users",
    "active_users",
    "chats",
    "messages",
    "tokens_today",
    "date",
)
SYSTEM_KEYS = (
    "cpu_percent",
    "memory_total",
    "memory_used",
    "memory_percent",
    "disk_total",
    "disk_used",
    "disk_percent",
    "uptime",
)


async def test_dashboard_admin_only(client, admin_headers):
    response = await client.get("/api/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    for key in DASHBOARD_KEYS:
        assert key in data, f"missing key: {key}"
    assert data["users"] >= 1


async def test_dashboard_regular_user_forbidden(client, user_headers):
    response = await client.get("/api/admin/dashboard", headers=user_headers)
    assert response.status_code == 403


async def test_dashboard_unauthenticated(client):
    response = await client.get("/api/admin/dashboard")
    assert response.status_code == 401


async def test_audit_logs(client, admin_headers):
    # Login (performed by the admin_headers fixture) writes an audit entry.
    response = await client.get("/api/admin/logs", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["logs"], list)
    actions = {log["action"] for log in data["logs"]}
    assert "login" in actions


async def test_audit_logs_filter_by_action(client, admin_headers, admin_user):
    # Create a user so a "user_created" audit entry is written.
    response = await client.post(
        "/api/users/",
        headers=admin_headers,
        json={
            "username": "bob",
            "password": "bob-password",
            "email": "bob@test.local",
            "display_name": "Bob",
            "role": "USER",
        },
    )
    assert response.status_code == 201

    filtered = await client.get("/api/admin/logs?action=user_created", headers=admin_headers)
    assert filtered.status_code == 200
    logs = filtered.json()["logs"]
    assert len(logs) >= 1
    assert all(log["action"] == "user_created" for log in logs)


async def test_audit_logs_forbidden_for_user(client, user_headers):
    response = await client.get("/api/admin/logs", headers=user_headers)
    assert response.status_code == 403


async def test_system_info(client, admin_headers):
    response = await client.get("/api/admin/system", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    for key in SYSTEM_KEYS:
        assert key in data, f"missing key: {key}"


async def test_system_info_forbidden_for_user(client, user_headers):
    response = await client.get("/api/admin/system", headers=user_headers)
    assert response.status_code == 403


async def test_admin_models(client, admin_headers):
    response = await client.get("/api/admin/models", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["models"], list)


async def test_admin_models_forbidden_for_user(client, user_headers):
    response = await client.get("/api/admin/models", headers=user_headers)
    assert response.status_code == 403