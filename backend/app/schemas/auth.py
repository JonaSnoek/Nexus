from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OIDCLoginRequest(BaseModel):
    code: str
    state: str


class SetupRequest(BaseModel):
    username: str
    password: str
    email: str
    display_name: str
