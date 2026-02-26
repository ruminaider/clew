"""OpenAI-compatible description provider for code enrichment.

Works with any OpenAI chat completions API-compatible endpoint:
OpenAI, OpenRouter, DeepSeek, Together, Groq, etc.
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

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIDescriptionProvider(DescriptionProvider):
    """OpenAI-compatible chat completions API description provider.

    Uses raw httpx (no SDK dependency) for maximum compatibility
    with any OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        max_concurrent: int = 5,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def model_name(self) -> str:
        return self._model

    async def _chat(self, prompt: str, max_tokens: int = 300) -> str | None:
        """Send a chat completion request and return the text response."""
        try:
            async with self._semaphore:
                response = await self._client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return None
                text = choices[0].get("message", {}).get("content", "")
                return text.strip() or None
        except Exception:
            logger.warning("OpenAI-compat API call failed", exc_info=True)
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
        return await self._chat(prompt, max_tokens=150)

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
        text = await self._chat(prompt, max_tokens=300)
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
