"""Image generation feature tests.

Covers the required scenarios:
- real end-to-end generation (fake provider) with quota charge + chat message
- permission gating (image.generate) + admin bypass
- not enough tokens -> 429 without any side effects
- provider error -> no bill (atomic refund), failed row kept
- provider not configured -> 503 before any reservation
- invalid prompt -> 400
- authenticated file serving (owner sees bytes, foreign user 403, anon 401)
- unlimited user is never blocked but usage is tracked
- admin settings masking + update (clear key, keep key)
- usage summary totals for chat vs image actions
- regenerate of an image message is rejected
- race condition: parallel image charges never exceed the quota
"""

import asyncio

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, Permission, UserPermission, GeneratedImage, Usage, UsageEvent
from app.services import user_service as user_service_module
from app.providers.images import ImageGenerationError, ImageResult


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 96 + b"IEND"


class FakeProvider:
    """Deterministic stand-in for the real OpenAI-compatible provider."""

    name = "fake_image_provider"

    def __init__(self, fail_error: str | None = None):
        self.fail_error = fail_error
        self.calls: list[dict] = []

    async def generate(self, prompt, model=None, size=None):
        self.calls.append({"prompt": prompt, "model": model, "size": size, "generated": True})
        if self.fail_error:
            raise ImageGenerationError(self.fail_error, status_code=502)
        return ImageResult(
            data=PNG_BYTES,
            width=512,
            height=512,
            provider=self.name,
            model=model or "dall-e-3",
        )

    async def healthcheck(self):
        return {"status": "ok", "provider": self.name}


async def _grant_image_permission(db: AsyncSession, user: User) -> None:
    permission = (
        await db.execute(select(Permission).where(Permission.name == "image.generate"))
    ).scalar_one_or_none()
    if permission is None:
        permission = Permission(name="image.generate", description="Generate images")
        db.add(permission)
        await db.commit()
        await db.refresh(permission)
    link = (
        await db.execute(
            select(UserPermission).where(
                UserPermission.user_id == user.id,
                UserPermission.permission_id == permission.id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        db.add(UserPermission(user_id=user.id, permission_id=permission.id))
        await db.commit()


async def _configure_provider(db: AsyncSession, api_key: str = "sk-test-secret-1234") -> None:
    from app.services.settings_service import set_setting
    await set_setting(db, "image_provider", "openai_compatible")
    await set_setting(db, "image_model", "dall-e-3")
    await set_setting(db, "image_api_url", "https://api.openai.com/v1")
    await set_setting(db, "image_api_key", api_key)


@pytest_asyncio.fixture
async def configured_images(db_session, monkeypatch):
    """Provider settings stored + fake provider installed."""
    await _configure_provider(db_session)

    provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.image_service.build_image_provider",
        lambda config: provider,
    )
    return provider


async def _create_chat(client, headers):
    resp = await client.post("/api/chat/", headers=headers, json={"title": "Image Chat"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _login_user(client, username, password):
    resp = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _set_usage(db: AsyncSession, user_id: int, tokens: int) -> None:
    db.add(Usage(
        user_id=user_id,
        period=user_service_module.CURRENT_PERIOD(),
        tokens_used=tokens,
        messages_used=0,
    ))
    await db.commit()


# ---------------------------------------------------------------------------
# End-to-end generation
# ---------------------------------------------------------------------------

async def test_generate_image_end_to_end(client, db_session, user_headers, regular_user, configured_images):
    await _grant_image_permission(db_session, regular_user)
    chat_id = await _create_chat(client, user_headers)

    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "A red fox in the snow", "chat_id": chat_id},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "done"
    assert data["prompt"] == "A red fox in the snow"
    assert data["token_cost"] == 10
    assert data["width"] == 512
    assert data["height"] == 512
    assert data["user_id"] == regular_user.id
    assert data["chat_id"] == chat_id
    assert data["url"] == f"/api/images/{data['id']}/file"

    # Quota result / ledger.
    me = (await client.get("/api/auth/me", headers=user_headers)).json()
    assert me["tokens_used_month"] == 10
    assert me["action_counts"] == {"IMAGE_GENERATION": 1}
    assert me["images_used_month"] == 1
    assert me["chat_messages_count_month"] == 0

    # The image shows inside the chat (assistant message references it).
    detail = (await client.get(f"/api/chat/{chat_id}", headers=user_headers)).json()
    image_msgs = [m for m in detail["messages"] if m.get("image_id") is not None]
    assert len(image_msgs) == 1
    assert image_msgs[0]["content"].startswith("Bildgenerierung:")
    assert image_msgs[0]["image"]["url"].endswith(f"{data['id']}/file")

    rows = (
        await db_session.execute(select(GeneratedImage).where(GeneratedImage.user_id == regular_user.id))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "done"
    assert rows[0].image_path is not None
    assert rows[0].bytes_size == len(PNG_BYTES)


async def test_generate_without_chat_still_persists(client, db_session, user_headers, regular_user, configured_images):
    await _grant_image_permission(db_session, regular_user)
    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "A lighthouse at night"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["chat_id"] is None
    meta = (await client.get(f"/api/images/{resp.json()['id']}", headers=user_headers)).json()
    assert meta["status"] == "done"


async def test_file_serving_owner_foreign_and_anon(
    client, db_session, admin_headers, user_headers, regular_user, configured_images
):
    await _grant_image_permission(db_session, regular_user)
    created = (await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "Mountain range"},
    )).json()
    image_id = created["id"]

    # Owner downloads the actual bytes.
    ok = await client.get(f"/api/images/{image_id}/file", headers=user_headers)
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/png"
    assert ok.content == PNG_BYTES

    # Another user that HAS the permission but does not own the image -> 403.
    from app.services.user_service import create_user
    intruder = await create_user(
        db_session, username="intruder", password="password123",
        display_name="Intruder", role="USER",
    )
    await _grant_image_permission(db_session, intruder)
    intruder_headers = await _login_user(client, "intruder", "password123")
    forbidden = await client.get(f"/api/images/{image_id}/file", headers=intruder_headers)
    assert forbidden.status_code == 403

    # Unauthenticated access is rejected.
    anon = await client.get(f"/api/images/{image_id}/file")
    assert anon.status_code in (401, 403)

    # Admins may fetch every image (role bypass).
    admin_file = await client.get(f"/api/images/{image_id}/file", headers=admin_headers)
    assert admin_file.status_code == 200


# ---------------------------------------------------------------------------
# Gating + errors
# ---------------------------------------------------------------------------

async def test_generation_requires_permission(client, db_session, user_headers, regular_user):
    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "nope"},
    )
    assert resp.status_code == 403
    images = (await db_session.execute(select(GeneratedImage))).scalars().all()
    events = (await db_session.execute(select(UsageEvent))).scalars().all()
    assert images == [] and events == []


async def test_not_enough_tokens_429_no_side_effects(
    client, db_session, user_headers, regular_user, configured_images
):
    await _grant_image_permission(db_session, regular_user)
    await _set_usage(db_session, regular_user.id, tokens=95)  # 95/100, cost 10

    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "will not happen"},
    )
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["error_code"] == "LIMIT_REACHED"
    assert detail["remaining"] == 5
    assert detail["action_type"] == "IMAGE_GENERATION"

    images = (await db_session.execute(select(GeneratedImage))).scalars().all()
    assert images == []
    usage = (await db_session.execute(
        select(Usage).where(
            Usage.user_id == regular_user.id,
            Usage.period == user_service_module.CURRENT_PERIOD(),
        )
    )).scalar_one()
    assert usage.tokens_used == 95


async def test_provider_error_refunds(client, db_session, user_headers, regular_user, configured_images):
    await _grant_image_permission(db_session, regular_user)
    configured_images.fail_error = "Internal generation error"

    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "will fail"},
    )
    assert resp.status_code == 502

    # The failure is durable...
    image = (await db_session.execute(select(GeneratedImage))).scalars().first()
    assert image is not None
    assert image.status == "failed"
    assert "Internal generation error" in image.error
    assert image.image_path is None

    # ...but the user was never billed (event deleted + counter refunded).
    events = (await db_session.execute(
        select(UsageEvent).where(UsageEvent.user_id == regular_user.id)
    )).scalars().all()
    assert events == []
    usage_rows = (await db_session.execute(
        select(Usage).where(Usage.user_id == regular_user.id)
    )).scalars().all()
    assert all(u.tokens_used == 0 for u in usage_rows)

    # Failed images have no bytes on disk -> 404.
    missing = await client.get(f"/api/images/{image.id}/file", headers=user_headers)
    assert missing.status_code == 404


async def test_provider_not_configured_503(client, db_session, user_headers, regular_user):
    # No configured_images fixture: defaults are provider "none".
    await _grant_image_permission(db_session, regular_user)

    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "nothing configured"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error_code"] == "IMAGE_PROVIDER_NOT_CONFIGURED"

    events = (await db_session.execute(select(UsageEvent))).scalars().all()
    images = (await db_session.execute(select(GeneratedImage))).scalars().all()
    assert events == [] and images == []


async def test_blank_prompt_400(client, db_session, user_headers, regular_user, configured_images):
    await _grant_image_permission(db_session, regular_user)
    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "   "},
    )
    assert resp.status_code == 400


async def test_unknown_chat_404(client, db_session, user_headers, regular_user, configured_images):
    await _grant_image_permission(db_session, regular_user)
    resp = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "orphan", "chat_id": 999999},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unlimited users
# ---------------------------------------------------------------------------

async def test_unlimited_user_generates_and_is_tracked(
    client, db_session, user_headers, regular_user, configured_images
):
    await _grant_image_permission(db_session, regular_user)
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.unlimited = True
    user.custom_monthly_token_limit = 1000
    await db_session.commit()

    for i in range(3):
        resp = await client.post(
            "/api/images/generate", headers=user_headers, json={"prompt": f"img {i}"}
        )
        assert resp.status_code == 201, resp.text

    me = (await client.get("/api/auth/me", headers=user_headers)).json()
    assert me["unlimited"] is True
    assert me["tokens_remaining"] is None
    assert me["tokens_used_month"] == 30  # 3 x 10 still tracked
    assert me["images_used_month"] == 3


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------

async def test_admin_image_settings_masking_and_update(client, admin_headers, user_headers, configured_images):
    settings_before = (await client.get("/api/admin/settings/images", headers=admin_headers)).json()
    assert settings_before["image_provider"] == "openai_compatible"
    assert settings_before["configured"] is True
    assert settings_before["has_api_key"] is True
    assert settings_before["api_key_tail"] == "1234"
    assert "image_api_key" not in settings_before  # raw key never leaks

    # Empty string on PUT clears the stored key.
    cleared = (await client.put(
        "/api/admin/settings/images", headers=admin_headers, json={"image_api_key": ""}
    )).json()
    assert cleared["has_api_key"] is False
    assert cleared["api_key_tail"] == ""

    # A new key is stored (and masked again).
    updated = (await client.put(
        "/api/admin/settings/images",
        headers=admin_headers,
        json={"image_api_key": "sk-live-9999", "image_model": "dall-e-3"},
    )).json()
    assert updated["has_api_key"] is True
    assert updated["api_key_tail"] == "9999"

    # Regular user may not read or change the provider configuration.
    assert (await client.get("/api/admin/settings/images", headers=user_headers)).status_code == 403
    assert (await client.put(
        "/api/admin/settings/images", headers=user_headers, json={"image_model": "evil-model"}
    )).status_code == 403


async def test_admin_usage_summary_breakdown(
    client, db_session, admin_headers, user_headers, regular_user, configured_images
):
    await _grant_image_permission(db_session, regular_user)
    chat_id = await _create_chat(client, user_headers)

    msg = await client.post(
        f"/api/chat/{chat_id}/messages", headers=user_headers, json={"content": "hi"}
    )
    assert msg.status_code == 200
    img = await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "Cat on a roof", "chat_id": chat_id},
    )
    assert img.status_code == 201

    summary = (await client.get("/api/admin/usage/summary", headers=admin_headers)).json()
    assert summary["total_tokens_used"] == 11
    assert summary["total_actions"] == 2
    assert summary["total_chat_actions"] == 1
    assert summary["total_image_actions"] == 1
    assert summary["total_chat_tokens"] == 1
    assert summary["total_image_tokens"] == 10

    row = next(u for u in summary["users"] if u["username"] == "user1")
    assert row["actions"].get("CHAT_MESSAGE") == 1
    assert row["actions"].get("IMAGE_GENERATION") == 1
    assert row["used"] == 11


# ---------------------------------------------------------------------------
# Regenerate guard
# ---------------------------------------------------------------------------

async def test_regenerate_image_message_rejected(client, db_session, user_headers, regular_user, configured_images):
    await _grant_image_permission(db_session, regular_user)
    chat_id = await _create_chat(client, user_headers)
    generated = (await client.post(
        "/api/images/generate",
        headers=user_headers,
        json={"prompt": "Sunset over the sea", "chat_id": chat_id},
    )).json()

    detail = (await client.get(f"/api/chat/{chat_id}", headers=user_headers)).json()
    image_msg = next(m for m in detail["messages"] if m["image_id"] == generated["id"])

    resp = await client.post(
        f"/api/chat/{chat_id}/messages/{image_msg['id']}/regenerate",
        headers=user_headers,
        json={},
    )
    assert resp.status_code == 400
    assert "nicht" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Race condition (parallel image charges)
# ---------------------------------------------------------------------------

async def test_parallel_image_requests_never_exceed_limit(
    client, db_session, user_headers, regular_user, monkeypatch
):
    await _grant_image_permission(db_session, regular_user)
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 10  # exactly one image fits (cost 10)
    await db_session.commit()
    await _configure_provider(db_session)

    provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.image_service.build_image_provider",
        lambda config: provider,
    )

    async def attempt():
        try:
            resp = await client.post(
                "/api/images/generate", headers=user_headers, json={"prompt": "race"}
            )
            return resp.status_code
        except Exception:
            return -1  # SQLite write contention between parallel sessions

    results = await asyncio.gather(*[attempt() for _ in range(8)])

    # Hard invariant: parallel requests never spend more than the quota.
    me = (await client.get("/api/auth/me", headers=user_headers)).json()
    assert me["tokens_used_month"] <= 10
    assert results.count(201) >= 1