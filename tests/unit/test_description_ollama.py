"""Tests for Ollama description provider."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from clew.clients.description_ollama import OllamaDescriptionProvider


def _make_chat_response(text: str) -> dict:
    """Build a minimal Ollama /api/chat response."""
    return {"message": {"role": "assistant", "content": text}}


@pytest.fixture
def provider() -> OllamaDescriptionProvider:
    return OllamaDescriptionProvider(
        base_url="http://localhost:11434",
        model="qwen3:8b",
        max_concurrent=5,
    )


class TestOllamaDescriptionProviderInit:
    def test_model_name(self, provider: OllamaDescriptionProvider) -> None:
        assert provider.model_name == "qwen3:8b"

    def test_custom_model(self) -> None:
        p = OllamaDescriptionProvider(model="llama3.1:8b")
        assert p.model_name == "llama3.1:8b"

    def test_base_url_trailing_slash_stripped(self) -> None:
        p = OllamaDescriptionProvider(base_url="http://localhost:11434/")
        assert p._base_url == "http://localhost:11434"


class TestGenerateDescription:
    @respx.mock
    async def test_success(self, provider: OllamaDescriptionProvider) -> None:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(200, json=_make_chat_response("Validates email format."))
        )
        result = await provider.generate_description(
            code='def validate_email(email): return "@" in email',
            language="python",
            entity_type="function",
            name="validate_email",
        )
        assert result == "Validates email format."

    @respx.mock
    async def test_sends_stream_false(self, provider: OllamaDescriptionProvider) -> None:
        route = respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(200, json=_make_chat_response("Desc."))
        )
        await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        import json

        body = json.loads(route.calls[0].request.content)
        assert body["stream"] is False
        assert body["model"] == "qwen3:8b"

    @respx.mock
    async def test_returns_none_on_error(self, provider: OllamaDescriptionProvider) -> None:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(500, json={"error": "model not found"})
        )
        result = await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert result is None

    @respx.mock
    async def test_returns_none_on_empty_content(
        self,
        provider: OllamaDescriptionProvider,
    ) -> None:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(200, json={"message": {"role": "assistant", "content": "  "}})
        )
        result = await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert result is None

    @respx.mock
    async def test_returns_none_on_connection_error(
        self,
        provider: OllamaDescriptionProvider,
    ) -> None:
        respx.post("http://localhost:11434/api/chat").mock(side_effect=ConnectionError("refused"))
        result = await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert result is None


class TestGenerateEnrichment:
    @respx.mock
    async def test_success(self, provider: OllamaDescriptionProvider) -> None:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(
                200,
                json=_make_chat_response(
                    "Description: Handles user login.\nKeywords: auth login session token"
                ),
            )
        )
        result = await provider.generate_enrichment(
            code="def login(user): pass",
            language="python",
            entity_type="function",
            name="login",
            file_path="auth/views.py",
            layer="view",
            app_name="auth",
        )
        assert result is not None
        desc, kw = result
        assert "login" in desc.lower()
        assert "auth" in kw

    @respx.mock
    async def test_returns_none_on_failure(self, provider: OllamaDescriptionProvider) -> None:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(500, json={"error": "timeout"})
        )
        result = await provider.generate_enrichment(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert result is None


class TestGenerateBatch:
    @respx.mock
    async def test_batch(self, provider: OllamaDescriptionProvider) -> None:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(200, json=_make_chat_response("A function."))
        )
        items = [
            {"code": "def a(): pass", "language": "python", "entity_type": "function", "name": "a"},
            {"code": "def b(): pass", "language": "python", "entity_type": "function", "name": "b"},
        ]
        results = await provider.generate_batch(items)
        assert len(results) == 2
        assert all(r == "A function." for r in results)
