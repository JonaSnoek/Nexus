from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "USER"
    monthly_token_limit: Optional[int] = Field(None, ge=0)
    monthly_message_limit: Optional[int] = Field(None, ge=0)


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool
    is_sso: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    monthly_token_limit: int
    monthly_message_limit: int
    limits_exempt: bool = False
    custom_monthly_token_limit: Optional[int] = None
    unlimited: bool = False

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


class PermissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    period: str
    tokens_used: int
    messages_used: int


class UsageEventResponse(BaseModel):
    id: int
    action_type: str
    tokens: int
    period: str
    created_at: Optional[datetime] = None
    metadata: Optional[str] = None


class UserLimitsResponse(BaseModel):
    user_id: int
    limits_exempt: bool
    custom_monthly_token_limit: Optional[int] = None
    unlimited: bool
    effective_token_limit: Optional[int] = None
    has_token_limit: bool
    tokens_used: int
    tokens_remaining: Optional[int] = None
    used_percent: Optional[int] = None
    monthly_message_limit: int
    messages_used: int


class MonthlyUsageResponse(BaseModel):
    period: str
    tokens_used_month: int
    messages_used_month: int
    monthly_token_limit: int
    monthly_message_limit: int
    tokens_remaining_month: Optional[int] = None
    messages_remaining_month: int
    limits_exempt: bool = False
    custom_monthly_token_limit: Optional[int] = None
    unlimited: bool = False
    has_token_limit: bool = True
    effective_token_limit: Optional[int] = None
    tokens_remaining: Optional[int] = None
    used_percent: Optional[int] = None


class UpdatePermissionsRequest(BaseModel):
    permission_ids: List[int]


class UpdateLimitsRequest(BaseModel):
    monthly_token_limit: Optional[int] = Field(None, ge=0)
    monthly_message_limit: Optional[int] = Field(None, ge=0)
    limits_exempt: Optional[bool] = None
    custom_monthly_token_limit: Optional[int] = Field(None, ge=0)
    unlimited: Optional[bool] = None