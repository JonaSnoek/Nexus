"""Image generation orchestration.

Flow (synchronous, every step server-side):

    1. resolve action cost          -> no charge without a cost value
    2. resolve provider config      -> misconfigured provider fails BEFORE any
                                       reservation (no bogus usage event)
    3. atomic quota reservation     -> race-condition safe check + charge
    4. create durable image row     -> the generation is tracked even if the
                                       provider crashes mid-flight
    5. provider.generate()          -> expensive work happens after reservation
    6. persist bytes + metadata     -> image is permanently assigned to the user
                                       and (optionally) the chat
    7. assistant chat message       -> the image is displayed inside the chat
    on failure                      -> status=failed + atomic refund, so the
                                       user never pays for a failed generation
"""

import time
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User, Chat, GeneratedImage
from app.providers.images import (
    ImageGenerationProvider,
    ImageGenerationError,
    build_image_provider,
)
from app.services.chat_service import add_message
from app.services.quota_service import build_limit_error
from app.services.settings_service import get_cost_for_action, get_image_provider_config
from app.services.user_service import spend_user_usage, LimitExceededError, refund_user_usage

MAX_IMAGE_BYTES = 20 * 1024 * 1024


async def get_active_image_provider(db: AsyncSession) -> ImageGenerationProvider:
    config = await get_image_provider_config(db)
    return build_image_provider(config)


def serialize_image(image: GeneratedImage) -> dict:
    return {
        "id": image.id,
        "user_id": image.user_id,
        "chat_id": image.chat_id,
        "status": image.status,
        "prompt": image.prompt,
        "provider": image.provider,
        "model": image.model,
        "width": image.width,
        "height": image.height,
        "bytes_size": image.bytes_size,
        "seconds": image.seconds,
        "token_cost": image.token_cost,
        "period": image.period,
        "error": image.error,
        "created_at": image.created_at,
        "url": f"/api/images/{image.id}/file",
    }


def _save_image_file(image_id: int, user_id: int, data: bytes) -> str:
    root = Path(settings.MEDIA_DIR)
    directory = root / "images" / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{image_id}.png"
    path.write_bytes(data)
    return str(path)


def _mark_failed(image: GeneratedImage, message: str) -> None:
    image.status = "failed"
    image.error = message[:2000]


async def _validate_chat(db: AsyncSession, user: User, chat_id: Optional[int]) -> Optional[Chat]:
    if chat_id is None:
        return None
    result = await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


async def generate_image(
    db: AsyncSession,
    user: User,
    prompt: str,
    chat_id: Optional[int] = None,
    model: Optional[str] = None,
    size: Optional[str] = None,
) -> Tuple[GeneratedImage, Optional[object]]:
    prompt = (prompt or "").strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der Bild-Prompt darf nicht leer sein.",
        )

    cost = await get_cost_for_action(db, "IMAGE_GENERATION")
    provider = await get_active_image_provider(db)  # raises 503 ImageGenerationError
    chat = await _validate_chat(db, user, chat_id)

    # 3. Atomic quota reservation (the race-condition-safe check + charge).
    try:
        event = await spend_user_usage(
            db, user, "IMAGE_GENERATION", cost,
            metadata={"source": "image_generation", "provider": provider.name, "model": model or ""},
        )
    except LimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=build_limit_error(exc.action_type, exc.cost, exc.limit, exc.used),
        )

    # 4. Durable image row (created before the expensive generation).
    image = GeneratedImage(
        user_id=user.id,
        chat_id=chat.id if chat else None,
        prompt=prompt,
        status="generating",
        token_cost=cost,
        period=event.period,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    # 5./6. Generate + persist. On failure: mark failed + atomic refund.
    try:
        started = time.monotonic()
        result = await provider.generate(prompt, model=model, size=size)
        seconds = round(time.monotonic() - started, 3)
        if len(result.data) > MAX_IMAGE_BYTES:
            raise ImageGenerationError("Generiertes Bild ist zu groß (Limit 20 MB).", status_code=502)
        image.status = "done"
        image.image_path = _save_image_file(image.id, user.id, result.data)
        image.width = result.width
        image.height = result.height
        image.bytes_size = len(result.data)
        image.seconds = seconds
        image.provider = result.provider or provider.name
        image.model = result.model or model or ""
        await db.commit()
        await db.refresh(image)
    except ImageGenerationError as exc:
        _mark_failed(image, exc.message)
        await refund_user_usage(db, user, event)
        raise exc
    except Exception as exc:  # noqa: BLE001 - any provider/storage failure
        _mark_failed(image, str(exc)[:2000] or "Unbekannter Fehler")
        await refund_user_usage(db, user, event)
        raise ImageGenerationError(
            f"Bildgenerierung fehlgeschlagen: {str(exc)[:500]}", status_code=502
        ) from exc

    # 7. Assistant message inside the chat references the generated image.
    message = None
    if chat is not None:
        message = await add_message(
            db, chat.id, "assistant", f"Bildgenerierung: {prompt}", tokens=0, image_id=image.id
        )

    return image, message


def image_file_path(image: GeneratedImage) -> Optional[str]:
    if image.status != "done" or not image.image_path:
        return None
    path = Path(image.image_path)
    return str(path) if path.is_file() else None