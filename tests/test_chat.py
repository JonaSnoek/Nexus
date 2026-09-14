"""Chat CRUD and messaging endpoint tests."""

from app.services.user_service import get_user_by_username


async def _create_chat(client, headers, title="Test Chat"):
    response = await client.post("/api/chat/", headers=headers, json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_create_chat(client, user_headers):
    response = await client.post(
        "/api/chat/", headers=user_headers, json={"title": "My Chat"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Chat"
    assert data["message_count"] == 0


async def test_list_chats(client, user_headers):
    chat1 = await _create_chat(client, user_headers, "Chat One")
    chat2 = await _create_chat(client, user_headers, "Chat Two")

    response = await client.get("/api/chat/", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    titles = {c["title"] for c in data["chats"]}
    assert titles == {"Chat One", "Chat Two"}


async def test_list_chats_other_user_sees_nothing(client, admin_headers):
    response = await client.get("/api/chat/", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_get_chat(client, user_headers, admin_headers):
    chat_id = await _create_chat(client, user_headers, "Detail Chat")
    response = await client.get(f"/api/chat/{chat_id}", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Detail Chat"
    assert data["messages"] == []

    # Another user cannot read this chat.
    forbidden = await client.get(f"/api/chat/{chat_id}", headers=admin_headers)
    assert forbidden.status_code == 404


async def test_get_chat_not_found(client, user_headers):
    response = await client.get("/api/chat/99999", headers=user_headers)
    assert response.status_code == 404


async def test_update_chat_title(client, user_headers):
    chat_id = await _create_chat(client, user_headers, "Before")
    response = await client.put(
        f"/api/chat/{chat_id}", headers=user_headers, json={"title": "After"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "After"

    # Confirm persisted.
    detail = await client.get(f"/api/chat/{chat_id}", headers=user_headers)
    assert detail.json()["title"] == "After"


async def test_delete_chat(client, user_headers):
    chat_id = await _create_chat(client, user_headers, "Doomed")
    response = await client.delete(f"/api/chat/{chat_id}", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "Chat deleted"

    missing = await client.get(f"/api/chat/{chat_id}", headers=user_headers)
    assert missing.status_code == 404


async def test_delete_chat_not_found(client, user_headers):
    response = await client.delete("/api/chat/99999", headers=user_headers)
    assert response.status_code == 404


async def test_send_message(client, user_headers):
    chat_id = await _create_chat(client, user_headers, "Stream Chat")
    response = await client.post(
        f"/api/chat/{chat_id}/messages",
        headers=user_headers,
        json={"content": "Hello NEXUS"},
    )
    assert response.status_code == 200

    body = response.text
    # The mock Ollama yields "Hello", " from", " NEXUS", so the stream must
    # contain those tokens followed by a "done" event.
    assert "Hello" in body
    assert '"type"' in body
    assert '"done"' in body

    detail = await client.get(f"/api/chat/{chat_id}", headers=user_headers)
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello NEXUS"
    assert messages[1]["role"] == "assistant"


async def test_send_message_to_nonexistent_chat(client, user_headers):
    response = await client.post(
        "/api/chat/99999/messages",
        headers=user_headers,
        json={"content": "Hello"},
    )
    assert response.status_code == 404


async def test_token_limit_enforced(client, user_headers, db_session):
    chat_id = await _create_chat(client, user_headers, "Token Limits")
    user = await get_user_by_username(db_session, "user1")
    user.daily_token_limit = 0
    await db_session.commit()

    response = await client.post(
        f"/api/chat/{chat_id}/messages",
        headers=user_headers,
        json={"content": "hello"},
    )
    assert response.status_code == 429
    assert "token limit" in response.json()["detail"]


async def test_message_limit_enforced(client, user_headers, db_session):
    chat_id = await _create_chat(client, user_headers, "Message Limits")
    user = await get_user_by_username(db_session, "user1")
    user.daily_message_limit = 0
    await db_session.commit()

    response = await client.post(
        f"/api/chat/{chat_id}/messages",
        headers=user_headers,
        json={"content": "hello"},
    )
    assert response.status_code == 429
    assert "message limit" in response.json()["detail"]