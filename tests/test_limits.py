"""Server-enforced quota / limits system tests.

Covers the required scenarios:
- standard default limit, custom limit, unlimited
- limit reached / not enough tokens / enough tokens
- monthly reset (period switch)
- race condition (parallel requests never overspend)
- permissions (regular users cannot change limits) + validation.
"""

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User, Usage, UsageEvent
from app.services import user_service as user_service_module
from app.services.user_service import (
    get_effective_token_limit,
    get_user_by_id,
    get_user_by_username,
    spend_user_usage,
    LimitExceededError,
    usage_view_for_user,
    usage_views_for_users,
    get_monthly_summary,
)
from app.services.settings_service import get_cost_for_action


def _next_period(period: str) -> str:
    year, month = int(period[:4]), int(period[5:7])
    month += 1
    if month > 12:
        month = 1
        year += 1
    return f"{year:04d}-{month:02d}"


async def _create_chat(client, headers, title="Limits Chat"):
    response = await client.post("/api/chat/", headers=headers, json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _send_chat_message(client, headers, chat_id, content="hello"):
    return await client.post(
        f"/api/chat/{chat_id}/messages", headers=headers, json={"content": content}
    )


async def _set_usage(db, user_id, tokens, messages=0):
    usage = Usage(
        user_id=user_id,
        period=user_service_module.CURRENT_PERIOD(),
        tokens_used=tokens,
        messages_used=messages,
    )
    db.add(usage)
    await db.commit()


# ---------------------------------------------------------------------------
# Effective limit: standard / custom / unlimited
# ---------------------------------------------------------------------------

async def test_standard_limit_uses_global_default(db_session, regular_user):
    user = await db_session.get(User, regular_user.id)
    limit = await get_effective_token_limit(db_session, user)
    assert limit == 100  # DEFAULTS["default_token_limit"]
    view = await usage_view_for_user(db_session, user)
    assert view["has_token_limit"] is True
    assert view["effective_token_limit"] == 100
    assert view["unlimited"] is False
    assert view["limits_exempt"] is False


async def test_custom_limit(db_session, regular_user):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 1000
    await db_session.commit()

    assert await get_effective_token_limit(db_session, user) == 1000
    views = await usage_views_for_users(db_session, [user])
    assert views[user.id]["effective_token_limit"] == 1000


async def test_batch_usage_views(db_session, regular_user, admin_user):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 1000
    admin = await db_session.get(User, admin_user.id)
    admin.unlimited = True
    await db_session.commit()

    views = await usage_views_for_users(db_session, [user, admin])
    assert views[user.id]["effective_token_limit"] == 1000
    assert views[user.id]["unlimited"] is False
    assert views[admin.id]["unlimited"] is True
    assert views[admin.id]["has_token_limit"] is False
    assert views[admin.id]["effective_token_limit"] is None


async def test_unlimited_user_is_never_blocked_but_usage_is_recorded(
    db_session, regular_user
):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.unlimited = True
    user.custom_monthly_token_limit = 1000
    await db_session.commit()

    assert await get_effective_token_limit(db_session, user) is None

    for _ in range(5):
        event = await spend_user_usage(db_session, user, "CHAT_MESSAGE", 1)

    rows = (
        await db_session.execute(select(UsageEvent).where(UsageEvent.user_id == user.id))
    ).scalars().all()
    assert len(rows) == 5  # usage continues to be tracked
    summary = await get_monthly_summary(db_session, user)
    assert summary["tokens_used_month"] == 5
    assert summary["unlimited"] is True
    assert summary["tokens_remaining"] is None


# ---------------------------------------------------------------------------
# Spend / quota behavior
# ---------------------------------------------------------------------------

async def test_spend_updates_counter_and_events(db_session, regular_user):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 100
    await db_session.commit()

    event = await spend_user_usage(db_session, user, "CHAT_MESSAGE", 3, metadata={"x": 1})
    assert event.tokens == 3
    assert event.action_type == "CHAT_MESSAGE"
    assert event.period == user_service_module.CURRENT_PERIOD()

    summary = await get_monthly_summary(db_session, user)
    assert summary["tokens_used_month"] == 3
    assert summary["tokens_remaining"] == 97


async def test_limit_reached_next_action_rejected(db_session, regular_user):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 100
    await db_session.commit()

    for _ in range(100):
        await spend_user_usage(db_session, user, "CHAT_MESSAGE", 1)

    with pytest.raises(LimitExceededError) as exc_info:
        await spend_user_usage(db_session, user, "CHAT_MESSAGE", 1)
    assert exc_info.value.used == 100
    assert exc_info.value.remaining == 0

    # Not exceeding the quota by 1 remains impossible too (e.g. image gen).
    with pytest.raises(LimitExceededError):
        await spend_user_usage(db_session, user, "IMAGE_GENERATION", 10)


async def test_image_generation_not_enough_tokens(db_session, regular_user):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 100
    await db_session.commit()
    await _set_usage(db_session, user.id, tokens=95)
    await db_session.refresh(user)

    cost = await get_cost_for_action(db_session, "IMAGE_GENERATION")
    assert cost == 10

    with pytest.raises(LimitExceededError) as exc_info:
        await spend_user_usage(db_session, user, "IMAGE_GENERATION", cost)
    assert exc_info.value.remaining == 5  # 100 - 95


async def test_image_generation_enough_tokens_charges_exactly(db_session, regular_user):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 100
    await db_session.commit()
    await _set_usage(db_session, user.id, tokens=90)
    await db_session.refresh(user)

    cost = await get_cost_for_action(db_session, "IMAGE_GENERATION")
    await spend_user_usage(db_session, user, "IMAGE_GENERATION", cost)

    summary = await get_monthly_summary(db_session, user)
    assert summary["tokens_used_month"] == 100
    assert summary["tokens_remaining"] == 0


async def test_monthly_reset(db_session, regular_user, monkeypatch):
    user = await db_session.get(User, regular_user.id)
    user.limits_exempt = True
    user.custom_monthly_token_limit = 100
    await db_session.commit()

    period_one = user_service_module.CURRENT_PERIOD()
    period_two = _next_period(period_one)

    for _ in range(100):
        await spend_user_usage(db_session, user, "CHAT_MESSAGE", 1)

    monkeypatch.setattr(user_service_module, "CURRENT_PERIOD", lambda: period_two)

    await spend_user_usage(db_session, user, "CHAT_MESSAGE", 7)

    rows = (
        await db_session.execute(select(Usage).order_by(Usage.period))
    ).scalars().all()
    by_period = {row.period: row.tokens_used for row in rows}
    assert by_period[period_one] == 100
    assert by_period[period_two] == 7

    view = await usage_view_for_user(db_session, user)
    assert view["period"] == period_two
    assert view["tokens_used_month"] == 7
    assert view["tokens_remaining"] == 93


# ---------------------------------------------------------------------------
# Race condition
# ---------------------------------------------------------------------------

async def test_race_condition_never_overspends(db_engine, regular_user):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as s:
        user = await s.get(User, regular_user.id)
        user.limits_exempt = True
        user.custom_monthly_token_limit = 10
        await s.commit()

    async def attempt():
        async with factory() as s:
            user = await s.get(User, regular_user.id)
            try:
                await spend_user_usage(s, user, "CHAT_MESSAGE", 1)
                return "ok"
            except LimitExceededError:
                return "limit"
            except Exception:
                return "error"  # SQLite write contention is acceptable

    results = await asyncio.gather(*[attempt() for _ in range(40)])

    async with factory() as s:
        usages = (
            await s.execute(select(Usage).where(Usage.user_id == regular_user.id))
        ).scalars().all()

    total = sum(row.tokens_used for row in usages)
    # The hard invariant: parallel requests never exceed the quota.
    assert total <= 10
    assert "ok" in results


# ---------------------------------------------------------------------------
# API round-trip: three states + validation + permissions
# ---------------------------------------------------------------------------

async def test_limits_api_three_states(client, admin_headers, regular_user):
    uid = regular_user.id

    # State B: custom limit.
    r = await client.put(
        f"/api/users/{uid}/limits",
        headers=admin_headers,
        json={"limits_exempt": True, "custom_monthly_token_limit": 1000, "unlimited": False},
    )
    assert r.status_code == 200
    cfg = (await client.get(f"/api/admin/users/{uid}/limits", headers=admin_headers)).json()
    assert cfg["limits_exempt"] is True
    assert cfg["custom_monthly_token_limit"] == 1000
    assert cfg["unlimited"] is False
    assert cfg["effective_token_limit"] == 1000
    assert cfg["has_token_limit"] is True

    # State C: unlimited must clear any custom value server-side.
    r = await client.put(
        f"/api/users/{uid}/limits",
        headers=admin_headers,
        json={"limits_exempt": True, "unlimited": True},
    )
    assert r.status_code == 200
    cfg = (await client.get(f"/api/admin/users/{uid}/limits", headers=admin_headers)).json()
    assert cfg["unlimited"] is True
    assert cfg["custom_monthly_token_limit"] is None
    assert cfg["effective_token_limit"] is None
    assert cfg["has_token_limit"] is False

    # Back to State A: custom + unlimited are reset server-side.
    r = await client.put(
        f"/api/users/{uid}/limits",
        headers=admin_headers,
        json={"limits_exempt": False},
    )
    assert r.status_code == 200
    cfg = (await client.get(f"/api/admin/users/{uid}/limits", headers=admin_headers)).json()
    assert cfg["limits_exempt"] is False
    assert cfg["unlimited"] is False
    assert cfg["custom_monthly_token_limit"] is None


async def test_limits_api_negative_values_rejected(client, admin_headers, regular_user):
    r = await client.put(
        f"/api/users/{regular_user.id}/limits",
        headers=admin_headers,
        json={"custom_monthly_token_limit": -5},
    )
    assert r.status_code == 422

    r = await client.put(
        "/api/admin/settings/limits",
        headers=admin_headers,
        json={"image_generation_cost": -1},
    )
    assert r.status_code == 422


async def test_regular_user_cannot_touch_limits(client, user_headers, admin_user, regular_user):
    r = await client.put(
        f"/api/users/{admin_user.id}/limits",
        headers=user_headers,
        json={"limits_exempt": True, "custom_monthly_token_limit": 5},
    )
    assert r.status_code == 403

    r = await client.get(f"/api/admin/users/{admin_user.id}/limits", headers=user_headers)
    assert r.status_code == 403

    r = await client.put(
        "/api/admin/settings/limits",
        headers=user_headers,
        json={"default_token_limit": 5},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# End-to-end: chat booking + events + admin statistics
# ---------------------------------------------------------------------------

async def test_chat_charges_one_cost_per_message(client, user_headers, regular_user):
    chat_id = await _create_chat(client, user_headers)
    resp = await _send_chat_message(client, user_headers, chat_id, "Hello NEXUS")
    assert resp.status_code == 200

    me = (await client.get("/api/auth/me", headers=user_headers)).json()
    assert me["has_token_limit"] is True
    assert me["effective_token_limit"] == 100
    assert me["tokens_used_month"] == 1
    assert me["tokens_remaining"] == 99
    assert me["unlimited"] is False

    events = (
        await client.get(f"/api/users/{regular_user.id}/usage/events", headers=user_headers)
    ).json()
    assert len(events) == 1
    assert events[0]["action_type"] == "CHAT_MESSAGE"
    assert events[0]["tokens"] == 1


async def test_admin_usage_summary(client, admin_headers, user_headers, regular_user):
    chat_id = await _create_chat(client, user_headers)
    await _send_chat_message(client, user_headers, chat_id, "ping")

    summary = (await client.get("/api/admin/usage/summary", headers=admin_headers)).json()
    assert summary["period"] == user_service_module.CURRENT_PERIOD()
    assert summary["total_tokens_used"] >= 1
    users_map = {u["username"]: u for u in summary["users"]}
    assert "user1" in users_map
    assert users_map["user1"]["used"] >= 1

    # A regular user must not see the global statistics.
    forbidden = await client.get("/api/admin/usage/summary", headers=user_headers)
    assert forbidden.status_code == 403


async def test_usage_events_endpoint_access_restriction(client, user_headers, admin_user):
    resp = await client.get(f"/api/users/{admin_user.id}/usage/events", headers=user_headers)
    assert resp.status_code == 403


async def test_me_reports_unlimited(client, user_headers, db_session):
    user = await get_user_by_username(db_session, "user1")
    user.limits_exempt = True
    user.unlimited = True
    user.custom_monthly_token_limit = 100
    await db_session.commit()

    me = (await client.get("/api/auth/me", headers=user_headers)).json()
    assert me["unlimited"] is True
    assert me["has_token_limit"] is False
    assert me["tokens_remaining"] is None
    assert me["used_percent"] is None