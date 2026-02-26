"""Ollama description provider for local LLM enrichment.

Uses Ollama's native /api/chat endpoint for code description generation.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from .description import (
    _DESCRIPTION_PROMPT,
    _ENRICHMENT_PROMPT,
    DescriptionProvider,
    parse_enrichment_response,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_URL = "http://localhost:11434"


class OllamaDescriptionProvider(DescriptionProvider):
    """Ollama native API description provider for local LLM enrichment.

    Uses /api/chat with stream=false for synchronous responses.
    Longer default timeout (120s) since local models are slower.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        model: str = DEFAULT_MODEL,
        max_concurrent: int = 5,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def model_name(self) -> str:
        return self._model

    async def _chat(self, prompt: str) -> str | None:
        """Send a chat request to Ollama and return the text response."""
        try:
            async with self._semaphore:
                response = await self._client.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("message", {}).get("content", "")
                return text.strip() or None
        except Exception:
            logger.warning("Ollama chat API call failed", exc_info=True)
            return None

    async def generate_description(
        self,
        code: str,
        language: str,
        entity_type: str,
        name: str,
    ) -> str | None:
        prompt = _DESCRIPTION_PROMPT.format(
            entity_type=entity_type,
            name=name,
            language=language,
            code=code,
        )
        return await self._chat(prompt)

    async def generate_enrichment(
        self,
        code: str,
        language: str,
        entity_type: str,
        name: str,
        *,
        file_path: str = "",
        layer: str = "",
        app_name: str = "",
        callers: str = "",
        callees: str = "",
        imports: str = "",
    ) -> tuple[str, str] | None:
        prompt = _ENRICHMENT_PROMPT.format(
            entity_type=entity_type,
            name=name,
            language=language,
            code=code,
            file_path=file_path,
            layer=layer,
            app_name=app_name,
            callers=callers or "(none)",
            callees=callees or "(none)",
            imports=imports or "(none)",
        )
        text = await self._chat(prompt)
        if not text:
            return None
        return parse_enrichment_response(text)

    async def generate_batch(self, items: list[dict[str, str]]) -> list[str | None]:
        tasks = [
            self.generate_description(
                code=item["code"],
                language=item["language"],
                entity_type=item["entity_type"],
                name=item["name"],
            )
            for item in items
        ]
        return list(await asyncio.gather(*tasks))
