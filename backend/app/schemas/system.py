from pydantic import BaseModel, Field
from typing import Optional


class HealthResponse(BaseModel):
    status: str
    database: str
    ollama: str
    setup_required: bool = False
    oidc_enabled: bool = False


class SystemInfoResponse(BaseModel):
    cpu_percent: Optional[float] = None
    memory_total: Optional[int] = None
    memory_used: Optional[int] = None
    memory_percent: Optional[float] = None
    disk_total: Optional[int] = None
    disk_used: Optional[int] = None
    disk_percent: Optional[float] = None
    uptime: Optional[float] = None


class SsoSettingsResponse(BaseModel):
    oidc_enabled: bool
    oidc_issuer_url: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_redirect_uri: str
    oidc_group_admins: str
    oidc_group_users: str


class SsoSettingsUpdate(BaseModel):
    oidc_enabled: Optional[bool] = None
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_redirect_uri: Optional[str] = None
    oidc_group_admins: Optional[str] = None
    oidc_group_users: Optional[str] = None


class DefaultLimitsResponse(BaseModel):
    default_token_limit: int
    default_message_limit: int
    chat_message_cost: int
    image_generation_cost: int


class DefaultLimitsUpdate(BaseModel):
    default_token_limit: Optional[int] = Field(None, ge=0)
    default_message_limit: Optional[int] = Field(None, ge=0)
    chat_message_cost: Optional[int] = Field(None, ge=0)
    image_generation_cost: Optional[int] = Field(None, ge=0)
