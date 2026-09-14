from pydantic import BaseModel
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
