from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    chat_id: Optional[int] = None
    model: Optional[str] = None
    size: Optional[str] = None


class GeneratedImageResponse(BaseModel):
    id: int
    user_id: int
    chat_id: Optional[int] = None
    status: str
    prompt: str
    provider: Optional[str] = None
    model: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    bytes_size: Optional[int] = None
    seconds: Optional[float] = None
    token_cost: int
    period: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    url: str

    class Config:
        from_attributes = True


class ImageProviderSettingsResponse(BaseModel):
    image_provider: str
    image_model: str
    image_api_url: str
    has_api_key: bool
    api_key_tail: str
    configured: bool


class ImageProviderSettingsUpdate(BaseModel):
    image_provider: Optional[str] = None
    image_model: Optional[str] = None
    image_api_url: Optional[str] = None
    image_api_key: Optional[str] = None