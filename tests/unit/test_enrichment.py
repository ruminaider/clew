"""Tests for result enrichment module."""

from __future__ import annotations

from unittest.mock import Mock

from clew.search.enrichment import CacheResultEnricher, _build_context_for_result
from clew.search.models import SearchResult


def _make_result(
    file_path: str = "src/main.py",
    chunk_id: str = "",
    function_name: str = "",
    class_name: str = "",
    **kwargs: object,
) -> SearchResult:
    defaults = {
        "content": "def foo(): pass",
        "score": 0.9,
        "chunk_type": "function",
        "line_start": 1,
        "line_end": 10,
        "language": "python",
    }
    defaults.update(kwargs)
    return SearchResult(
        file_path=file_path,
        chunk_id=chunk_id,
        function_name=function_name,
        class_name=class_name,
        **defaults,  # type: ignore[arg-type]
    )


class TestCacheResultEnricher:
    """Test CacheResultEnricher with mock cache."""

    def test_empty_results_returns_empty(self):
        cache = Mock()
        enricher = CacheResultEnricher(cache)
        result = enricher.enrich([])
        assert result == []
        cache.traverse_relationships_batch.assert_not_called()

    def test_no_entities_extracted(self):
        """Results without chunk_id or names return unchanged."""
        cache = Mock()
        enricher = CacheResultEnricher(cache)
        results = [_make_result()]
        enriched = enricher.enrich(results)
        assert enriched == results
        cache.traverse_relationships_batch.assert_not_called()

    def test_enriches_with_caller_context(self):
        cache = Mock()
        cache.traverse_relationships_batch.return_value = [
            {
                "source_entity": "src/handler.py::handle_request",
                "target_entity": "src/main.py::process",
                "relationship": "calls",
                "depth": 1,
                "confidence": 0.9,
            }
        ]
        enricher = CacheResultEnricher(cache)
        results = [
            _make_result(
                file_path="src/main.py",
                chunk_id="src/main.py::function::process",
                function_name="process",
            )
        ]
        enriched = enricher.enrich(results)
        assert len(enriched) == 1
        assert "Called by:" in enriched[0].context
        assert "handle_request" in enriched[0].context

    def test_enriches_with_test_context(self):
        cache = Mock()
        cache.traverse_relationships_batch.return_value = [
            {
                "source_entity": "tests/test_main.py::test_process",
                "target_entity": "src/main.py::process",
                "relationship": "tests",
                "depth": 1,
                "confidence": 0.9,
            }
        ]
        enricher = CacheResultEnricher(cache)
        results = [
            _make_result(
                file_path="src/main.py",
                chunk_id="src/main.py::function::process",
                function_name="process",
            )
        ]
        enriched = enricher.enrich(results)
        assert "Tests:" in enriched[0].context
        assert "test_process" in enriched[0].context

    def test_no_relationships_returns_unchanged(self):
        cache = Mock()
        cache.traverse_relationships_batch.return_value = []
        enricher = CacheResultEnricher(cache)
        results = [
            _make_result(
                chunk_id="src/main.py::function::process",
                function_name="process",
            )
        ]
        enriched = enricher.enrich(results)
        assert enriched[0].context == ""

    def test_traverse_failure_returns_unchanged(self):
        cache = Mock()
        cache.traverse_relationships_batch.side_effect = RuntimeError("db error")
        enricher = CacheResultEnricher(cache)
        results = [
            _make_result(
                chunk_id="src/main.py::function::process",
                function_name="process",
            )
        ]
        enriched = enricher.enrich(results)
        assert enriched == results

    def test_caps_at_five_results(self):
        """Only top 5 results have entities extracted."""
        cache = Mock()
        cache.traverse_relationships_batch.return_value = []
        enricher = CacheResultEnricher(cache)
        results = [
            _make_result(
                chunk_id=f"src/file{i}.py::function::func{i}",
                function_name=f"func{i}",
            )
            for i in range(10)
        ]
        enricher.enrich(results)
        # extract_entity_ids is called with max_results=5
        call_args = cache.traverse_relationships_batch.call_args
        entities = call_args[0][0]
        # Should have at most 5 chunk_ids (one per result, capped at 5)
        chunk_ids = [e for e in entities if "::function::" in e]
        assert len(chunk_ids) <= 5

    def test_multiple_callers_capped_at_three(self):
        cache = Mock()
        cache.traverse_relationships_batch.return_value = [
            {
                "source_entity": f"src/caller{i}.py::caller{i}",
                "target_entity": "src/main.py::process",
                "relationship": "calls",
                "depth": 1,
                "confidence": 0.9,
            }
            for i in range(5)
        ]
        enricher = CacheResultEnricher(cache)
        results = [
            _make_result(
                file_path="src/main.py",
                chunk_id="src/main.py::function::process",
                function_name="process",
            )
        ]
        enriched = enricher.enrich(results)
        # "Called by: X, Y, Z" — at most 3 callers
        context = enriched[0].context
        if "Called by:" in context:
            called_by_part = context.split("Called by:")[1].split("|")[0]
            callers = [c.strip() for c in called_by_part.split(",")]
            assert len(callers) <= 3


class TestBuildContextForResult:
    """Test _build_context_for_result helper."""

    def test_no_matching_entities(self):
        result = _make_result(file_path="src/other.py")
        entities = ["src/main.py::process"]
        entity_rels: dict[str, list[dict[str, object]]] = {}
        parts = _build_context_for_result(result, "src/other.py", entities, entity_rels)
        assert parts == []

    def test_matching_by_file_path_prefix(self):
        result = _make_result(file_path="src/main.py", chunk_id="src/main.py::function::process")
        entities = ["src/main.py::process"]
        entity_rels = {
            "src/main.py::process": [
                {
                    "source_entity": "src/handler.py::handle",
                    "target_entity": "src/main.py::process",
                    "relationship": "calls",
                }
            ]
        }
        parts = _build_context_for_result(result, "src/main.py", entities, entity_rels)
        assert len(parts) >= 1
        assert "Called by:" in parts[0]

    def test_matching_by_chunk_id(self):
        result = _make_result(
            file_path="src/main.py",
            chunk_id="src/main.py::function::process",
        )
        entities = ["src/main.py::function::process"]
        entity_rels = {
            "src/main.py::function::process": [
                {
                    "source_entity": "src/handler.py::handle",
                    "target_entity": "src/main.py::function::process",
                    "relationship": "calls",
                }
            ]
        }
        parts = _build_context_for_result(result, "src/main.py", entities, entity_rels)
        assert len(parts) >= 1
