"""Tests for ignore pattern loading and matching."""

from pathlib import Path

import pytest

from code_search.indexer.ignore import DEFAULT_IGNORE_PATTERNS, IgnorePatternLoader


class TestDefaultPatterns:
    def test_defaults_include_pycache(self) -> None:
        assert "__pycache__/" in DEFAULT_IGNORE_PATTERNS

    def test_defaults_include_node_modules(self) -> None:
        assert "node_modules/" in DEFAULT_IGNORE_PATTERNS

    def test_defaults_include_git(self) -> None:
        assert ".git/" in DEFAULT_IGNORE_PATTERNS


class TestIgnorePatternLoader:
    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_default_patterns_applied(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("__pycache__/module.pyc")
        assert loader.should_ignore("node_modules/pkg/index.js")

    def test_gitignore_loaded(self, project_root: Path) -> None:
        (project_root / ".gitignore").write_text("*.log\nbuild/\n")
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("app.log")
        assert loader.should_ignore("build/output.js")

    def test_codesearchignore_loaded(self, project_root: Path) -> None:
        (project_root / ".codesearchignore").write_text("*.generated.py\n")
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("output.generated.py")

    def test_config_excludes_applied(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(
            project_root, config_excludes=["**/migrations/**"]
        )
        loader.load()
        assert loader.should_ignore("backend/app/migrations/0001.py")

    def test_env_var_override(self, project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODE_SEARCH_EXCLUDE", "*.tmp,*.bak")
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("data.tmp")
        assert loader.should_ignore("backup.bak")

    def test_non_matching_file_not_ignored(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert not loader.should_ignore("src/models.py")

    def test_comments_and_blanks_skipped(self, project_root: Path) -> None:
        (project_root / ".gitignore").write_text(
            "# This is a comment\n\n*.log\n  \n"
        )
        loader = IgnorePatternLoader(project_root)
        loader.load()
        assert loader.should_ignore("app.log")

    def test_lazy_load_on_should_ignore(self, project_root: Path) -> None:
        loader = IgnorePatternLoader(project_root)
        # Don't call load() explicitly — should_ignore triggers it
        assert loader.should_ignore("__pycache__/foo.pyc")
