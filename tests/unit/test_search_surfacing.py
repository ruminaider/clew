"""Tests for clew.search.surfacing module."""

from __future__ import annotations

from unittest.mock import Mock

from clew.search.surfacing import categorize_relationship, surface_peripherals


def _mock_search_result(**overrides):
    """Create a mock SearchResult with defaults."""
    defaults = {
        "file_path": "src/main.py",
        "chunk_id": "src/main.py::function::hello",
        "class_name": "",
        "function_name": "hello",
    }
    defaults.update(overrides)
    return Mock(**defaults)


class TestSurfacePeripherals:
    def test_returns_related_files(self):
        result = _mock_search_result()
        cache = Mock()
        cache.traverse_relationships_batch.return_value = [
            {
                "source_entity": "src/main.py::function::hello",
                "relationship": "tests",
                "target_entity": "tests/test_main.py::TestHello",
                "confidence": "static",
                "depth": 1,
            }
        ]

        related = surface_peripherals([result], cache)
        assert len(related) == 1
        assert related[0]["file_path"] == "tests/test_main.py"
        assert related[0]["relationship"] == "tests"

    def test_empty_results_returns_empty(self):
        cache = Mock()
        assert surface_peripherals([], cache) == []

    def test_excludes_files_already_in_results(self):
        result = _mock_search_result(
            file_path="src/main.py", chunk_id="src/main.py::function::hello"
        )
        cache = Mock()
        cache.traverse_relationships_batch.return_value = [
            {
                "source_entity": "src/main.py::function::hello",
                "relationship": "calls",
                "target_entity": "src/main.py::function::helper",
                "confidence": "static",
                "depth": 1,
            }
        ]

        related = surface_peripherals([result], cache)
        assert len(related) == 0

    def test_caps_at_max_files(self):
        result = _mock_search_result()
        cache = Mock()
        cache.traverse_relationships_batch.return_value = [
            {
                "source_entity": "src/main.py::function::hello",
                "relationship": "calls",
                "target_entity": f"lib/module{i}.py::func{i}",
                "confidence": "static",
                "depth": 1,
            }
            for i in range(10)
        ]

        related = surface_peripherals([result], cache, max_files=5)
        assert len(related) <= 5

    def test_handles_traverse_failure(self):
        result = _mock_search_result()
        cache = Mock()
        cache.traverse_relationships_batch.side_effect = Exception("DB error")

        related = surface_peripherals([result], cache)
        assert related == []

    def test_uses_class_name_function_name_entity(self):
        result = _mock_search_result(
            chunk_id="",
            class_name="MyClass",
            function_name="my_method",
            file_path="src/app.py",
        )
        cache = Mock()
        cache.traverse_relationships_batch.return_value = []

        surface_peripherals([result], cache)
        entities = cache.traverse_relationships_batch.call_args[0][0]
        assert "src/app.py::MyClass.my_method" in entities

    def test_no_entities_returns_empty(self):
        result = Mock(file_path="src/main.py", chunk_id="", class_name="", function_name="")
        cache = Mock()

        related = surface_peripherals([result], cache)
        assert related == []
        cache.traverse_relationships_batch.assert_not_called()


class TestCategorizeRelationship:
    def test_test_file(self):
        assert categorize_relationship("calls", "tests/test_main.py") == "tests"

    def test_admin_file(self):
        assert categorize_relationship("calls", "src/admin.py") == "admin"

    def test_config_file(self):
        assert categorize_relationship("calls", "src/config.py") == "config"

    def test_constants_file(self):
        assert categorize_relationship("calls", "src/constants.py") == "config"

    def test_scripts_file(self):
        assert categorize_relationship("calls", "scripts/deploy.py") == "scripts"

    def test_fallback_to_relationship(self):
        assert categorize_relationship("imports", "src/utils.py") == "imports"
