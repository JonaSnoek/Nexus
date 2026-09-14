import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.chat import (
    ChatCreate, ChatUpdate, ChatResponse, ChatListResponse,
    ChatDetailResponse, SendMessageRequest, RegenerateRequest, MessageResponse,
)
from app.services.chat_service import (
    create_chat, get_chat, list_chats, count_chats, update_chat, delete_chat,
    add_message, get_messages, get_message, delete_message, delete_messages_after,
)
from app.services.user_service import check_message_limit, spend_user_usage, increment_usage, LimitExceededError
from app.services.settings_service import get_cost_for_action
from app.services.audit_service import log_action
from app.providers.ollama import OllamaProvider

router = APIRouter(prefix="/api/chat", tags=["chat"])
provider = OllamaProvider()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) + len(text) // 4)


_ACTION_LABELS = {
    "CHAT_MESSAGE": "diese Nachricht",
    "IMAGE_GENERATION": "diese Bildgenerierung",
}


def _build_limit_error(action_type: str, cost: int, limit, used: int) -> dict:
    remaining = max(limit - used, 0) if limit is not None else None
    label = _ACTION_LABELS.get(action_type, "diese Aktion")
    if remaining is not None and remaining < cost:
        message = (
            f"Für {label} werden {cost} Tokens benötigt. "
            f"Dir stehen nur noch {remaining} Tokens zur Verfügung."
        )
    else:
        message = (
            f"Dein monatliches Token-Limit ist erreicht. "
            f"Verbraucht: {used} / {limit} Tokens. "
            f"Bitte wende dich an einen Administrator."
        )
    return {
        "error_code": "LIMIT_REACHED",
        "action_type": action_type,
        "cost": cost,
        "monthly_limit": limit,
        "used": used,
        "remaining": remaining,
        "message": message,
    }


async def _reserve_action(db, user, action_type: str, metadata: Optional[dict] = None):
    """Server-side quota enforcement. The LLM is only called after the quota
    for the action was atomically reserved; the charge always happens before
    any expensive work and can never be bypassed from the client."""
    cost = await get_cost_for_action(db, action_type)
    try:
        return await spend_user_usage(db, user, action_type, cost, metadata)
    except LimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_build_limit_error(exc.action_type, exc.cost, exc.limit, exc.used),
        )


@router.get("/", response_model=ChatListResponse)
async def list_user_chats(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chats = await list_chats(db, current_user.id, skip, limit)
    total = await count_chats(db, current_user.id)
    response_chats = []
    for chat in chats:
        msg_count = len(chat.messages) if hasattr(chat, "messages") and chat.messages else 0
        response_chats.append(
            ChatResponse(
                id=chat.id,
                title=chat.title,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                message_count=msg_count,
            )
        )
    return ChatListResponse(chats=response_chats, total=total)


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_new_chat(
    body: ChatCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat = await create_chat(db, current_user.id, body.title)
    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=0,
    )


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat_detail(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat = await get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    messages = [
        MessageResponse(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            tokens=m.tokens or 0,
            created_at=m.created_at,
        )
        for m in chat.messages
    ]
    return ChatDetailResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=messages,
    )


@router.put("/{chat_id}", response_model=ChatResponse)
async def update_chat_title(
    chat_id: int,
    body: ChatUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat = await get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    chat = await update_chat(db, chat, body.title)
    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=len(chat.messages) if hasattr(chat, "messages") and chat.messages else 0,
    )


@router.delete("/{chat_id}")
async def delete_existing_chat(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat = await get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    await delete_chat(db, chat)
    await log_action(db, "chat_deleted", user_id=current_user.id, details=f"Deleted chat {chat_id}")
    return {"detail": "Chat deleted"}


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: int,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat = await get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    if not await check_message_limit(db, current_user):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Monthly message limit reached")

    user_tokens = _estimate_tokens(body.content)
    model = body.model or settings.NEXUS_LLM_MODEL

    # Enforce + reserve the monthly quota BEFORE talking to the LLM.
    await _reserve_action(
        db, current_user, "CHAT_MESSAGE",
        metadata={"source": "chat_message", "estimated_tokens": user_tokens, "model": model},
    )

    await add_message(db, chat_id, "user", body.content, user_tokens)
    await increment_usage(db, current_user.id, tokens=0, messages=1)

    history = await get_messages(db, chat_id)
    messages_for_llm = []
    for msg in history:
        role_val = msg.role.value if hasattr(msg.role, "value") else msg.role
        messages_for_llm.append({"role": role_val, "content": msg.content})

    async def event_stream():
        full_response = ""
        try:
            async for token in provider.chat_stream(messages_for_llm, model):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        assistant_tokens = _estimate_tokens(full_response)
        await add_message(db, chat_id, "assistant", full_response, assistant_tokens)

        yield f"data: {json.dumps({'type': 'done', 'tokens': assistant_tokens})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{chat_id}/messages/{message_id}/regenerate")
async def regenerate_message(
    chat_id: int,
    message_id: int,
    body: RegenerateRequest = RegenerateRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat = await get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    message = await get_message(db, chat_id, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    role_val = message.role.value if hasattr(message.role, "value") else message.role
    if role_val != "assistant":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only regenerate assistant messages")

    if not await check_message_limit(db, current_user):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Monthly message limit reached")

    model = body.model or settings.NEXUS_LLM_MODEL

    # Enforce + reserve the monthly quota BEFORE regenerating.
    await _reserve_action(
        db, current_user, "CHAT_MESSAGE",
        metadata={"source": "regenerate", "model": model},
    )

    await delete_messages_after(db, chat_id, message_id)

    history = await get_messages(db, chat_id)
    messages_for_llm = []
    for msg in history:
        rv = msg.role.value if hasattr(msg.role, "value") else msg.role
        messages_for_llm.append({"role": rv, "content": msg.content})

    async def event_stream():
        full_response = ""
        try:
            async for token in provider.chat_stream(messages_for_llm, model):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        assistant_tokens = _estimate_tokens(full_response)
        await add_message(db, chat_id, "assistant", full_response, assistant_tokens)

        yield f"data: {json.dumps({'type': 'done', 'tokens': assistant_tokens})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{chat_id}/messages/{message_id}")
async def delete_existing_message(
    chat_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat = await get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    message = await get_message(db, chat_id, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    await delete_message(db, message)
    return {"detail": "Message deleted"}
