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

_ENRICHMENT_PROMPT = (
    "Generate a description and search keywords for this code entity.\n"
    "\n"
    "Entity: {name}\n"
    "Type: {entity_type}\n"
    "File: {file_path} ({layer} layer, {app_name} app)\n"
    "Called by: {callers}\n"
    "Calls: {callees}\n"
    "Imports: {imports}\n"
    "\n"
    "```{language}\n"
    "{code}\n"
    "```\n"
    "\n"
    "Respond in exactly this format:\n"
    "Description: <2-3 sentences: what it does, why it exists, what domain concept it represents>\n"
    "Keywords: <8-15 space-separated terms a developer might search for>"
)


def parse_enrichment_response(text: str) -> tuple[str, str]:
    """Parse a Description + Keywords response.

    Returns (description, keywords) tuple.
    Falls back gracefully if format is unexpected.
    """
    description = ""
    keywords = ""

    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("description:"):
            description = stripped[len("description:") :].strip()
        elif stripped.lower().startswith("keywords:"):
            keywords = stripped[len("keywords:") :].strip()

    # If no structured format found, use entire text as description
    if not description and not keywords:
        description = text.strip()

    return description, keywords


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
        """Generate description + keywords with relationship context.

        Returns (description, keywords) tuple, or None if generation fails.
        """
        # Default implementation falls back to generate_description
        desc = await self.generate_description(code, language, entity_type, name)
        if desc:
            return desc, ""
        return None

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
        import anthropic

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
            block = response.content[0]
            if not hasattr(block, "text"):
                return None
            text: str = block.text.strip()
            return text if text else None
        except Exception:
            logger.warning(
                "Failed to generate description for %s '%s'",
                entity_type,
                name,
                exc_info=True,
            )
            return None

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
        """Generate description + keywords with relationship context."""
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
        try:
            async with self._semaphore:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )
            block = response.content[0]
            if not hasattr(block, "text"):
                return None
            text: str = block.text.strip()
            if not text:
                return None
            return parse_enrichment_response(text)
        except Exception:
            logger.warning(
                "Failed to generate enrichment for %s '%s'",
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
