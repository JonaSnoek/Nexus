import secrets
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://nexus:nexus@postgres:5432/nexus"
    SECRET_KEY: str = Field(
        default=secrets.token_urlsafe(32),
        validation_alias=AliasChoices("SECRET_KEY", "NEXUS_SECRET_KEY"),
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OLLAMA_URL: str = "http://ollama:11434"
    NEXUS_LLM_MODEL: str = "qwen3:8b"

    OIDC_ENABLED: bool = False
    OIDC_ISSUER_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = ""
    OIDC_GROUP_ADMINS: str = "admins"
    OIDC_GROUP_USERS: str = "users"

    NEXUS_PORT: int = 3000

    FIRST_ADMIN_USERNAME: str = ""
    FIRST_ADMIN_PASSWORD: str = ""
    FIRST_ADMIN_EMAIL: str = ""

    IMAGE_PROVIDER: str = "none"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
