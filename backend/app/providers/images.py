"""Swappable image generation providers.

Only the transport lives here: providers receive a prompt and return raw image
bytes. All quota handling, file storage and usage ledger logic is done by
``app.services.image_service``, so a different backend (local diffusion, another
vendor, ...) can be plugged in without touching the API or the UI.

``build_image_provider`` is the factory used by the service. Provider selection
and parameters are controlled via the admin panel (system_settings), never hard
coded in the UI.
"""

from abc import ABC, abstractmethod
import base64
import binascii
from dataclasses import dataclass
from typing import Optional

import httpx


class ImageGenerationError(Exception):
    """A user-facing image generation failure.

    ``status_code`` maps to the HTTP response status; ``error_code`` is an
    optional machine readable key (e.g. LIMIT_REACHED).
    """

    def __init__(
        self,
        message: str = "Bildgenerierung fehlgeschlagen",
        status_code: int = 502,
        error_code: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


@dataclass
class ImageResult:
    """Raw image bytes plus optional metadata returned by a provider."""

    data: bytes
    width: Optional[int] = None
    height: Optional[int] = None
    provider: str = ""
    model: str = ""


class ImageGenerationProvider(ABC):
    """Interface every image generator must implement."""

    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
    ) -> ImageResult:
        """Generate an image from the prompt. Raises ImageGenerationError."""

    @abstractmethod
    async def healthcheck(self) -> dict:
        """Return a simple status dict for the admin diagnostics."""


def _png_dimensions(data: bytes):
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None, None


class OpenAICompatibleImageProvider(ImageGenerationProvider):
    """Real image provider for any OpenAI-compatible ``/images/generations`` API.

    Works with OpenAI (DALL-E) as well as self-hosted OpenAI-compatible image
    backends. The response is either ``b64_json`` or a ``url`` (downloaded and
    capped at ``max_bytes``).
    """

    name = "openai_compatible"
    DEFAULT_MODEL = "dall-e-3"
    DEFAULT_SIZE = "1024x1024"
    GENERATION_TIMEOUT = 180.0
    DOWNLOAD_TIMEOUT = 120.0
    MAX_BYTES = 20 * 1024 * 1024

    def __init__(
        self,
        api_url: str,
        api_key: str = "",
        model: str = "",
    ):
        base_url = (api_url or "").strip().rstrip("/")
        if not base_url:
            raise ImageGenerationError(
                "Bildgenerierung ist nicht konfiguriert (API-URL fehlt).",
                status_code=503,
            )
        # Accept a bare host, a /v1 base or a full /images/generations URL.
        if base_url.endswith("/images/generations"):
            self.endpoint = base_url
        elif base_url.endswith("/v1"):
            self.endpoint = f"{base_url}/images/generations"
        else:
            self.endpoint = f"{base_url}/v1/images/generations"
        self.api_key = api_key or ""
        self.model = (model or "").strip() or self.DEFAULT_MODEL

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
    ) -> ImageResult:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": (model or "").strip() or self.model,
            "prompt": prompt,
            "n": 1,
            "size": size or self.DEFAULT_SIZE,
            "response_format": "b64_json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.GENERATION_TIMEOUT) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
            if response.status_code in (401, 403):
                raise ImageGenerationError(
                    "Bildprovider hat den API-Key abgelehnt (401/403).", status_code=502
                )
            if response.status_code == 404:
                raise ImageGenerationError(
                    "Bildprovider: Modell nicht gefunden (404).", status_code=502
                )
            response.raise_for_status()
            data = response.json()
        except ImageGenerationError:
            raise
        except httpx.TimeoutException:
            raise ImageGenerationError(
                "Bildprovider antwortet nicht (Timeout).", status_code=504
            )
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                f"Bildprovider nicht erreichbar: {exc}", status_code=502
            )
        except ValueError:
            raise ImageGenerationError(
                "Bildprovider lieferte eine ungültige Antwort.", status_code=502
            )

        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise ImageGenerationError(
                "Bildprovider lieferte keine Bilddaten.", status_code=502
            )
        content = items[0]

        raw = None
        b64 = content.get("b64_json")
        if isinstance(b64, str) and b64:
            try:
                raw = base64.b64decode(b64)
            except (binascii.Error, ValueError):
                raise ImageGenerationError(
                    "Bildprovider lieferte ungültige Bilddaten.", status_code=502
                )
        elif isinstance(content.get("url"), str) and content["url"]:
            raw = await self._download(content["url"])

        if not raw:
            raise ImageGenerationError(
                "Bildprovider lieferte keine Bilddaten.", status_code=502
            )
        if len(raw) > self.MAX_BYTES:
            raise ImageGenerationError(
                "Generiertes Bild ist zu groß (Limit 20 MB).", status_code=502
            )

        width, height = _png_dimensions(raw)
        return ImageResult(
            data=raw,
            width=width,
            height=height,
            provider=self.name,
            model=(model or "").strip() or self.model,
        )

    async def _download(self, url: str) -> bytes:
        chunks: list[bytes] = []
        total = 0
        try:
            async with httpx.AsyncClient(timeout=self.DOWNLOAD_TIMEOUT) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self.MAX_BYTES:
                            raise ImageGenerationError(
                                "Generiertes Bild ist zu groß (Limit 20 MB).", status_code=502
                            )
                        chunks.append(chunk)
        except ImageGenerationError:
            raise
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                f"Bild-Download fehlgeschlagen: {exc}", status_code=502
            )
        return b"".join(chunks)

    async def healthcheck(self) -> dict:
        return {
            "provider": self.name,
            "endpoint": self.endpoint,
            "api_key_configured": bool(self.api_key),
            "status": "configured" if self.endpoint else "misconfigured",
        }


def build_image_provider(config: dict) -> ImageGenerationProvider:
    """Factory: instantiate the provider selected in the admin settings."""
    provider_name = (config.get("image_provider") or "none").strip().lower()
    if provider_name == "openai_compatible":
        return OpenAICompatibleImageProvider(
            api_url=config.get("image_api_url") or "",
            api_key=config.get("image_api_key") or "",
            model=config.get("image_model") or "",
        )
    raise ImageGenerationError(
        "Bildgenerierung ist nicht konfiguriert. Bitte in den "
        "Admin-Einstellungen einen Bildprovider einrichten.",
        status_code=503,
        error_code="IMAGE_PROVIDER_NOT_CONFIGURED",
    )