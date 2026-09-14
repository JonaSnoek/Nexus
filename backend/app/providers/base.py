from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, List


class BaseAIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, model: str, **kwargs: Any) -> str:
        pass

    @abstractmethod
    async def stream(self, prompt: str, model: str, **kwargs: Any) -> AsyncIterator[str]:
        pass

    @abstractmethod
    async def healthcheck(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def list_models(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def pull_model(self, model_name: str) -> bool:
        pass
