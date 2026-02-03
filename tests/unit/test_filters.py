"""Tests for Qdrant filter construction."""

from __future__ import annotations

import pytest

from code_search.exceptions import InvalidFilterError
from code_search.search.filters import FILTERABLE_FIELDS, build_qdrant_filter


class TestBuildQdrantFilter:
    def test_empty_filters_returns_none(self) -> None:
        result = build_qdrant_filter({})

        assert result is None

    def test_single_language_filter(self) -> None:
        result = build_qdrant_filter({"language": "python"})

        assert result is not None
        assert len(result.must) == 1
        condition = result.must[0]
        assert condition.key == "language"
        assert condition.match.value == "python"

    def test_multiple_filters(self) -> None:
        result = build_qdrant_filter({"language": "python", "chunk_type": "function"})

        assert result is not None
        assert len(result.must) == 2
        keys = {c.key for c in result.must}
        assert keys == {"language", "chunk_type"}

    def test_is_test_bool_conversion_true(self) -> None:
        result = build_qdrant_filter({"is_test": "true"})

        assert result is not None
        condition = result.must[0]
        assert condition.key == "is_test"
        assert condition.match.value is True

    def test_is_test_bool_conversion_false(self) -> None:
        result = build_qdrant_filter({"is_test": "false"})

        assert result is not None
        condition = result.must[0]
        assert condition.key == "is_test"
        assert condition.match.value is False

    def test_invalid_key_raises_error(self) -> None:
        with pytest.raises(InvalidFilterError):
            build_qdrant_filter({"invalid_key": "val"})

    def test_all_filterable_fields(self) -> None:
        filters = {field: "test_value" for field in FILTERABLE_FIELDS}
        result = build_qdrant_filter(filters)

        assert result is not None
        assert len(result.must) == len(FILTERABLE_FIELDS)
        keys = {c.key for c in result.must}
        assert keys == FILTERABLE_FIELDS

    def test_is_test_case_insensitive(self) -> None:
        for value in ("True", "TRUE", "tRuE"):
            result = build_qdrant_filter({"is_test": value})

            assert result is not None
            condition = result.must[0]
            assert condition.match.value is True, f"Failed for is_test={value!r}"
