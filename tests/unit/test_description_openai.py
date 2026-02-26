"""Tests for OpenAI-compatible description provider."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from clew.clients.description_openai import OpenAIDescriptionProvider


def _make_chat_response(text: str) -> dict:
    """Build a minimal OpenAI chat completions response."""
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
    }


@pytest.fixture
def provider() -> OpenAIDescriptionProvider:
    return OpenAIDescriptionProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        max_concurrent=5,
    )


class TestOpenAIDescriptionProviderInit:
    def test_model_name(self, provider: OpenAIDescriptionProvider) -> None:
        assert provider.model_name == "gpt-4o-mini"

    def test_custom_model(self) -> None:
        p = OpenAIDescriptionProvider(api_key="k", model="deepseek-chat")
        assert p.model_name == "deepseek-chat"

    def test_base_url_trailing_slash_stripped(self) -> None:
        p = OpenAIDescriptionProvider(api_key="k", base_url="https://api.example.com/v1/")
        assert p._base_url == "https://api.example.com/v1"


class TestGenerateDescription:
    @respx.mock
    async def test_success(self, provider: OpenAIDescriptionProvider) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
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
    async def test_auth_header_sent(self, provider: OpenAIDescriptionProvider) -> None:
        route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json=_make_chat_response("Desc."))
        )
        await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"

    @respx.mock
    async def test_returns_none_on_error(self, provider: OpenAIDescriptionProvider) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(401, json={"error": {"message": "Unauthorized"}})
        )
        result = await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert result is None

    @respx.mock
    async def test_returns_none_on_empty_choices(
        self,
        provider: OpenAIDescriptionProvider,
    ) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json={"choices": []})
        )
        result = await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert result is None

    @respx.mock
    async def test_returns_none_on_whitespace_response(
        self,
        provider: OpenAIDescriptionProvider,
    ) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json=_make_chat_response("   \n  "))
        )
        result = await provider.generate_description(
            code="def f(): pass",
            language="python",
            entity_type="function",
            name="f",
        )
        assert result is None


class TestGenerateEnrichment:
    @respx.mock
    async def test_success(self, provider: OpenAIDescriptionProvider) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(
                200,
                json=_make_chat_response(
                    "Description: Processes orders.\nKeywords: order process ecommerce"
                ),
            )
        )
        result = await provider.generate_enrichment(
            code="def process_order(): pass",
            language="python",
            entity_type="function",
            name="process_order",
            file_path="app/orders.py",
            layer="service",
            app_name="app",
        )
        assert result is not None
        desc, kw = result
        assert "Processes orders" in desc
        assert "order" in kw

    @respx.mock
    async def test_returns_none_on_failure(self, provider: OpenAIDescriptionProvider) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(500, json={"error": {"message": "Server error"}})
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
    async def test_batch(self, provider: OpenAIDescriptionProvider) -> None:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=Response(200, json=_make_chat_response("A function."))
        )
        items = [
            {"code": "def a(): pass", "language": "python", "entity_type": "function", "name": "a"},
            {"code": "def b(): pass", "language": "python", "entity_type": "function", "name": "b"},
        ]
        results = await provider.generate_batch(items)
        assert len(results) == 2
        assert all(r == "A function." for r in results)


class TestCustomBaseUrl:
    @respx.mock
    async def test_openrouter_url(self) -> None:
        """Custom base_url routes requests to the right endpoint."""
        p = OpenAIDescriptionProvider(
            api_key="or-key",
            model="anthropic/claude-haiku-4-5",
            base_url="https://openrouter.ai/api/v1",
        )
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=Response(200, json=_make_chat_response("A helper."))
        )
        result = await p.generate_description(
            code="def helper(): pass",
            language="python",
            entity_type="function",
            name="helper",
        )
        assert result == "A helper."
