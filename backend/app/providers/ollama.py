import json
from typing import AsyncIterator, Dict, Any, List
import httpx
from app.providers.base import BaseAIProvider
from app.core.config import settings


class OllamaProvider(BaseAIProvider):
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_URL

    async def generate(self, prompt: str, model: str, **kwargs: Any) -> str:
        async with httpx.AsyncClient(timeout=300.0) as client:
            payload: Dict[str, Any] = {
                "model": model or settings.NEXUS_LLM_MODEL,
                "prompt": prompt,
                "stream": False,
            }
            if "system" in kwargs:
                payload["system"] = kwargs["system"]
            if "context" in kwargs:
                payload["context"] = kwargs["context"]
            if "options" in kwargs:
                payload["options"] = kwargs["options"]

            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def stream(self, prompt: str, model: str, **kwargs: Any) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=300.0) as client:
            payload: Dict[str, Any] = {
                "model": model or settings.NEXUS_LLM_MODEL,
                "prompt": prompt,
                "stream": True,
            }
            if "system" in kwargs:
                payload["system"] = kwargs["system"]
            if "context" in kwargs:
                payload["context"] = kwargs["context"]
            if "options" in kwargs:
                payload["options"] = kwargs["options"]

            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield token
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=300.0) as client:
            payload: Dict[str, Any] = {
                "model": model or settings.NEXUS_LLM_MODEL,
                "messages": messages,
                "stream": True,
            }
            if "options" in kwargs:
                payload["options"] = kwargs["options"]

            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            message = data.get("message", {})
                            token = message.get("content", "")
                            if token:
                                yield token
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

    async def healthcheck(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    return {"status": "ok", "details": response.json()}
                return {"status": "error", "details": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "details": str(e)}

    async def list_models(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            return [
                {
                    "name": m.get("name", ""),
                    "size": m.get("size", 0),
                    "digest": m.get("digest", ""),
                    "modified_at": m.get("modified_at", ""),
                }
                for m in models
            ]

    async def pull_model(self, model_name: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False},
                )
                response.raise_for_status()
                return True
        except Exception:
            return False

    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"name": model_name},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e)}
