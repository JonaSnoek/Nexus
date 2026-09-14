from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "USER"
    monthly_token_limit: Optional[int] = None
    monthly_message_limit: Optional[int] = None


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


class MonthlyUsageResponse(BaseModel):
    period: str
    tokens_used_month: int
    messages_used_month: int
    monthly_token_limit: int
    monthly_message_limit: int
    tokens_remaining_month: int
    messages_remaining_month: int


class UpdatePermissionsRequest(BaseModel):
    permission_ids: List[int]


class UpdateLimitsRequest(BaseModel):
    monthly_token_limit: Optional[int] = None
    monthly_message_limit: Optional[int] = None