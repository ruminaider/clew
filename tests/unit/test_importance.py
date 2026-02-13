"""Tests for importance scoring module."""

from clew.indexer.importance import compute_importance_scores


class TestComputeImportanceScores:
    def test_empty_graph_returns_empty_dict(self) -> None:
        result = compute_importance_scores([])
        assert result == {}

    def test_single_edge(self) -> None:
        pairs = [("a.py::foo", "b.py::bar")]
        result = compute_importance_scores(pairs)
        assert result == {"b.py": 1.0}

    def test_multiple_inbound_edges_same_file(self) -> None:
        pairs = [
            ("a.py::foo", "b.py::bar"),
            ("c.py::baz", "b.py::qux"),
            ("d.py::thing", "b.py::other"),
        ]
        result = compute_importance_scores(pairs)
        assert result["b.py"] == 1.0

    def test_scores_bounded_zero_to_one(self) -> None:
        pairs = [
            ("a.py::f1", "b.py::g1"),
            ("a.py::f2", "b.py::g2"),
            ("a.py::f3", "c.py::h1"),
        ]
        result = compute_importance_scores(pairs)
        for score in result.values():
            assert 0.0 <= score <= 1.0

    def test_relative_scores(self) -> None:
        """File with more incoming edges gets higher score."""
        pairs = [
            ("a.py::f1", "popular.py::g1"),
            ("b.py::f2", "popular.py::g2"),
            ("c.py::f3", "popular.py::g3"),
            ("d.py::f4", "unpopular.py::h1"),
        ]
        result = compute_importance_scores(pairs)
        assert result["popular.py"] > result["unpopular.py"]
        assert result["popular.py"] == 1.0
        assert result["unpopular.py"] == pytest.approx(1.0 / 3.0)

    def test_target_without_separator_used_as_file_path(self) -> None:
        """Targets without :: are treated as file-level entities."""
        pairs = [("a.py::foo", "some_module")]
        result = compute_importance_scores(pairs)
        assert "some_module" in result
        assert result["some_module"] == 1.0

    def test_max_file_gets_score_one(self) -> None:
        """The file with the most inbound edges always gets score 1.0."""
        pairs = [
            ("x.py::a", "core.py::b"),
            ("y.py::c", "core.py::d"),
            ("z.py::e", "core.py::f"),
            ("w.py::g", "core.py::h"),
            ("x.py::a", "util.py::i"),
        ]
        result = compute_importance_scores(pairs)
        assert result["core.py"] == 1.0
        assert result["util.py"] == 0.25


import pytest  # noqa: E402
