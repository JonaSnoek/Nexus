from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseImageProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        pass

    @abstractmethod
    async def healthcheck(self) -> dict:
        pass


class PlaceholderImageProvider(BaseImageProvider):
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        return "[Image generation not configured. Set IMAGE_PROVIDER to enable image generation.]"

    async def healthcheck(self) -> dict:
        return {"status": "placeholder", "message": "No image provider configured"}
