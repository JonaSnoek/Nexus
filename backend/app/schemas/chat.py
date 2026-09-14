from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ChatCreate(BaseModel):
    title: Optional[str] = "New Chat"


class ChatUpdate(BaseModel):
    title: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    tokens: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    chats: List[ChatResponse]
    total: int


class ChatDetailResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]


class SendMessageRequest(BaseModel):
    content: str
    model: Optional[str] = None


class RegenerateRequest(BaseModel):
    model: Optional[str] = None
