"""Description generation providers for natural language code summaries."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

_DESCRIPTION_PROMPT = (
    "Generate a concise 1-2 sentence natural language description"
    " of this {entity_type}.\n"
    "Focus on WHAT it does and WHY, not HOW."
    " Write as if for a code search index.\n"
    "\n"
    "{entity_type}: {name}\n"
    "Language: {language}\n"
    "\n"
    "```{language}\n"
    "{code}\n"
    "```\n"
    "\n"
    "Description:"
)


class DescriptionProvider(ABC):
    """Abstract base class for description generation providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...

    @abstractmethod
    async def generate_description(
        self,
        code: str,
        language: str,
        entity_type: str,
        name: str,
    ) -> str | None:
        """Generate a natural language description for a code entity.

        Returns None if generation fails.
        """
        ...

    async def generate_batch(self, items: list[dict[str, str]]) -> list[str | None]:
        """Generate descriptions for multiple items concurrently.

        Default implementation calls generate_description sequentially.
        Subclasses may override for concurrent execution.
        """
        results: list[str | None] = []
        for item in items:
            result = await self.generate_description(
                code=item["code"],
                language=item["language"],
                entity_type=item["entity_type"],
                name=item["name"],
            )
            results.append(result)
        return results


class AnthropicDescriptionProvider(DescriptionProvider):
    """Anthropic Claude description provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 150,
        max_concurrent: int = 5,
    ) -> None:
        import anthropic  # type: ignore[import-not-found]

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._semaphore = asyncio.Semaphore(max_concurrent)

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_description(
        self,
        code: str,
        language: str,
        entity_type: str,
        name: str,
    ) -> str | None:
        """Generate a description using Anthropic Claude."""
        prompt = _DESCRIPTION_PROMPT.format(
            entity_type=entity_type,
            name=name,
            language=language,
            code=code,
        )
        try:
            async with self._semaphore:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
            text = response.content[0].text.strip()
            return text if text else None
        except Exception:
            logger.warning(
                "Failed to generate description for %s '%s'",
                entity_type,
                name,
                exc_info=True,
            )
            return None

    async def generate_batch(self, items: list[dict[str, str]]) -> list[str | None]:
        """Generate descriptions concurrently with semaphore throttling."""
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
