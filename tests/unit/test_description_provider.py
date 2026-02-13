"""Tests for description generation providers."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clew.clients.description import DescriptionProvider


@pytest.fixture()
def mock_anthropic() -> MagicMock:
    """Provide a mock anthropic module in sys.modules."""
    mock_module = MagicMock()
    with patch.dict(sys.modules, {"anthropic": mock_module}):
        yield mock_module


def _make_provider(
    mock_anthropic: MagicMock,
    *,
    api_key: str = "test-key",
    model: str | None = None,
    max_tokens: int = 150,
    max_concurrent: int = 5,
) -> AnthropicDescriptionProvider:  # noqa: F821
    """Create an AnthropicDescriptionProvider with the mocked anthropic module."""
    from clew.clients.description import AnthropicDescriptionProvider

    kwargs: dict[str, object] = {"api_key": api_key}
    if model is not None:
        kwargs["model"] = model
    kwargs["max_tokens"] = max_tokens
    kwargs["max_concurrent"] = max_concurrent
    return AnthropicDescriptionProvider(**kwargs)  # type: ignore[arg-type]


class TestDescriptionProviderABC:
    """Test the ABC cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            DescriptionProvider()  # type: ignore[abstract]


class TestAnthropicDescriptionProvider:
    """Test Anthropic Claude description provider."""

    def test_model_name(self, mock_anthropic: MagicMock) -> None:
        provider = _make_provider(mock_anthropic)
        assert provider.model_name == "claude-sonnet-4-5-20250929"

    def test_custom_model(self, mock_anthropic: MagicMock) -> None:
        provider = _make_provider(mock_anthropic, model="claude-haiku-4-5-20251001")
        assert provider.model_name == "claude-haiku-4-5-20251001"

    async def test_generate_description(self, mock_anthropic: MagicMock) -> None:
        provider = _make_provider(mock_anthropic)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Validate an email address format.")]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await provider.generate_description(
                code='def validate_email(email: str) -> bool:\n    return "@" in email',
                language="python",
                entity_type="function",
                name="validate_email",
            )

        assert result == "Validate an email address format."
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
        assert call_kwargs["max_tokens"] == 150

    async def test_generate_description_strips_whitespace(self, mock_anthropic: MagicMock) -> None:
        provider = _make_provider(mock_anthropic)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="  Check user permissions.  \n")]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await provider.generate_description(
                code="def check_perms(): pass",
                language="python",
                entity_type="function",
                name="check_perms",
            )

        assert result == "Check user permissions."

    async def test_generate_description_returns_none_on_error(
        self, mock_anthropic: MagicMock
    ) -> None:
        provider = _make_provider(mock_anthropic)

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("API error")
            result = await provider.generate_description(
                code="def broken(): pass",
                language="python",
                entity_type="function",
                name="broken",
            )

        assert result is None

    async def test_generate_description_returns_none_on_empty(
        self, mock_anthropic: MagicMock
    ) -> None:
        provider = _make_provider(mock_anthropic)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="   ")]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await provider.generate_description(
                code="def empty(): pass",
                language="python",
                entity_type="function",
                name="empty",
            )

        assert result is None

    async def test_generate_batch(self, mock_anthropic: MagicMock) -> None:
        provider = _make_provider(mock_anthropic)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="A description.")]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            items = [
                {
                    "code": "def a(): pass",
                    "language": "python",
                    "entity_type": "function",
                    "name": "a",
                },
                {
                    "code": "def b(): pass",
                    "language": "python",
                    "entity_type": "function",
                    "name": "b",
                },
            ]
            results = await provider.generate_batch(items)

        assert len(results) == 2
        assert all(r == "A description." for r in results)

    async def test_generate_batch_respects_concurrency(self, mock_anthropic: MagicMock) -> None:
        """Verify semaphore limits concurrency in generate_batch."""
        provider = _make_provider(mock_anthropic, max_concurrent=2)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Desc.")]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            items = [
                {
                    "code": f"def f{i}(): pass",
                    "language": "python",
                    "entity_type": "function",
                    "name": f"f{i}",
                }
                for i in range(5)
            ]
            results = await provider.generate_batch(items)

        assert len(results) == 5
        assert mock_create.call_count == 5

    async def test_generate_enrichment(self, mock_anthropic: MagicMock) -> None:
        """Test enrichment generates description + keywords with relationship context."""
        provider = _make_provider(mock_anthropic)

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=(
                    "Description: Processes incoming orders and dispatches notifications.\n"
                    "Keywords: order processing dispatch notification ecommerce workflow"
                )
            )
        ]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await provider.generate_enrichment(
                code="def process_order(order_id): pass",
                language="python",
                entity_type="function",
                name="process_order",
                file_path="ecomm/utils.py",
                layer="service",
                app_name="ecomm",
                callers="views.checkout",
                callees="tasks.void_order, notifications.send_email",
                imports="models.Order",
            )

        assert result is not None
        desc, keywords = result
        assert "Processes incoming orders" in desc
        assert "order" in keywords

        # Verify the prompt includes relationship context
        call_kwargs = mock_create.call_args[1]
        prompt = call_kwargs["messages"][0]["content"]
        assert "Called by: views.checkout" in prompt
        assert "Calls: tasks.void_order" in prompt
        assert "Imports: models.Order" in prompt

    async def test_generate_enrichment_returns_none_on_error(
        self, mock_anthropic: MagicMock
    ) -> None:
        provider = _make_provider(mock_anthropic)

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("API error")
            result = await provider.generate_enrichment(
                code="def broken(): pass",
                language="python",
                entity_type="function",
                name="broken",
            )

        assert result is None

    async def test_generate_enrichment_empty_relationships(self, mock_anthropic: MagicMock) -> None:
        """Enrichment works with empty relationship fields."""
        provider = _make_provider(mock_anthropic)

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="Description: A simple helper.\nKeywords: helper utility")
        ]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await provider.generate_enrichment(
                code="def helper(): pass",
                language="python",
                entity_type="function",
                name="helper",
            )

        assert result is not None
        desc, keywords = result
        assert desc == "A simple helper."
        assert keywords == "helper utility"

        # Verify empty relationships show as (none) in prompt
        call_kwargs = mock_create.call_args[1]
        prompt = call_kwargs["messages"][0]["content"]
        assert "(none)" in prompt


class TestParseEnrichmentResponse:
    """Test enrichment response parsing."""

    def test_standard_format(self) -> None:
        from clew.clients.description import parse_enrichment_response

        text = "Description: Processes orders.\nKeywords: order process ecommerce"
        desc, kw = parse_enrichment_response(text)
        assert desc == "Processes orders."
        assert kw == "order process ecommerce"

    def test_unstructured_fallback(self) -> None:
        from clew.clients.description import parse_enrichment_response

        text = "This is a free-form description without labels."
        desc, kw = parse_enrichment_response(text)
        assert desc == text
        assert kw == ""

    def test_extra_whitespace(self) -> None:
        from clew.clients.description import parse_enrichment_response

        text = "  Description:   Handles auth.  \n  Keywords:   auth login token  "
        desc, kw = parse_enrichment_response(text)
        assert desc == "Handles auth."
        assert kw == "auth login token"

    def test_case_insensitive(self) -> None:
        from clew.clients.description import parse_enrichment_response

        text = "description: Does stuff.\nkeywords: thing stuff"
        desc, kw = parse_enrichment_response(text)
        assert desc == "Does stuff."
        assert kw == "thing stuff"
