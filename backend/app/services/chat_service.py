from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import Chat, Message, MessageRole, GeneratedImage


async def create_chat(db: AsyncSession, user_id: int, title: str = "New Chat") -> Chat:
    chat = Chat(user_id=user_id, title=title)
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


async def get_chat(db: AsyncSession, chat_id: int, user_id: int) -> Optional[Chat]:
    result = await db.execute(
        select(Chat)
        .options(
            selectinload(Chat.messages).selectinload(Message.image),
            selectinload(Chat.images),
        )
        .where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_chats(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 50) -> List[Chat]:
    result = await db.execute(
        select(Chat)
        .options(selectinload(Chat.messages))
        .where(Chat.user_id == user_id)
        .order_by(Chat.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_chats(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(select(func.count(Chat.id)).where(Chat.user_id == user_id))
    return result.scalar()


async def update_chat(db: AsyncSession, chat: Chat, title: str) -> Chat:
    chat.title = title
    chat.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(chat)
    return chat


async def delete_chat(db: AsyncSession, chat: Chat) -> None:
    await db.delete(chat)
    await db.commit()


async def add_message(
    db: AsyncSession,
    chat_id: int,
    role: str,
    content: str,
    tokens: int = 0,
    image_id: Optional[int] = None,
) -> Message:
    message = Message(
        chat_id=chat_id,
        role=MessageRole(role),
        content=content,
        tokens=tokens,
        image_id=image_id,
    )
    db.add(message)
    chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_result.scalar_one_or_none()
    if chat:
        chat.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(message)
    return message


async def get_messages(db: AsyncSession, chat_id: int) -> List[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def get_message(db: AsyncSession, chat_id: int, message_id: int) -> Optional[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id, Message.chat_id == chat_id)
    )
    return result.scalar_one_or_none()


async def delete_message(db: AsyncSession, message: Message) -> None:
    await db.delete(message)
    await db.commit()


async def delete_messages_after(db: AsyncSession, chat_id: int, message_id: int) -> None:
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id, Message.id >= message_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    for msg in messages:
        await db.delete(msg)
    await db.commit()
