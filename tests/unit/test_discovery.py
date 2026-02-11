"""Tests for centralized file discovery."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from clew.discovery import discover_files
from clew.models import ProjectConfig, SafetyConfig


class TestDiscoverFiles:
    def test_finds_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("x = 1")
        config = ProjectConfig()

        result = discover_files(tmp_path, config)

        assert tmp_path / "app.py" in result
        assert tmp_path / "utils.py" in result

    def test_finds_typescript_files(self, tmp_path: Path) -> None:
        (tmp_path / "index.ts").write_text("const x = 1;")
        (tmp_path / "App.tsx").write_text("export default App;")
        config = ProjectConfig()

        result = discover_files(tmp_path, config)

        assert tmp_path / "index.ts" in result
        assert tmp_path / "App.tsx" in result

    def test_filters_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "notes.txt").write_text("note")
        (tmp_path / "app.py").write_text("x = 1")
        config = ProjectConfig()

        result = discover_files(tmp_path, config)

        assert tmp_path / "data.json" not in result
        assert tmp_path / "notes.txt" not in result
        assert tmp_path / "app.py" in result

    def test_respects_gitignore(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("ignored_dir/\n")
        ignored_dir = tmp_path / "ignored_dir"
        ignored_dir.mkdir()
        (ignored_dir / "module.py").write_text("x = 1")
        (tmp_path / "kept.py").write_text("y = 2")
        config = ProjectConfig()

        result = discover_files(tmp_path, config)

        assert tmp_path / "ignored_dir" / "module.py" not in result
        assert tmp_path / "kept.py" in result

    def test_respects_security_excludes(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=abc")
        (tmp_path / ".env.local").write_text("SECRET=abc")
        (tmp_path / "app.py").write_text("x = 1")
        config = ProjectConfig()

        # .env files match the default security pattern **/.env*
        # but they also need to have a matching extension to be discovered.
        # Since .env has no matching extension, it would be filtered by extension
        # already. Let's use extensions that include all to test security filtering.
        result = discover_files(tmp_path, config, extensions={".env", ".env.local", ".py"})

        # .env* files should be excluded by security patterns
        assert tmp_path / ".env" not in result
        assert tmp_path / ".env.local" not in result
        assert tmp_path / "app.py" in result

    def test_skips_oversized_files(self, tmp_path: Path) -> None:
        small_file = tmp_path / "small.py"
        small_file.write_text("x = 1")
        big_file = tmp_path / "big.py"
        big_file.write_text("x" * 2048)
        config = ProjectConfig(safety=SafetyConfig(max_file_size_bytes=1024))

        result = discover_files(tmp_path, config)

        assert small_file in result
        assert big_file not in result

    def test_returns_sorted_paths(self, tmp_path: Path) -> None:
        (tmp_path / "zebra.py").write_text("z = 1")
        (tmp_path / "alpha.py").write_text("a = 1")
        (tmp_path / "middle.py").write_text("m = 1")
        config = ProjectConfig()

        result = discover_files(tmp_path, config)

        assert result == sorted(result)

    def test_custom_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "config.json").write_text("{}")
        config = ProjectConfig()

        result = discover_files(tmp_path, config, extensions={".json"})

        assert tmp_path / "data.json" in result
        assert tmp_path / "config.json" in result
        assert tmp_path / "app.py" not in result

    def test_empty_directory(self, tmp_path: Path) -> None:
        config = ProjectConfig()

        result = discover_files(tmp_path, config)

        assert result == []

    def test_respects_clewignore(self, tmp_path: Path) -> None:
        (tmp_path / ".clewignore").write_text("*.generated.py\n")
        (tmp_path / "output.generated.py").write_text("x = 1")
        (tmp_path / "app.py").write_text("y = 2")
        config = ProjectConfig()

        result = discover_files(tmp_path, config)

        assert tmp_path / "output.generated.py" not in result
        assert tmp_path / "app.py" in result


def _git_init_and_add(repo: Path, *filenames: str) -> None:
    """Initialize a git repo and add the named files."""
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True
    )
    for fn in filenames:
        subprocess.run(["git", "add", fn], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=repo,
        capture_output=True,
        check=True,
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
class TestGitAwareDiscovery:
    """Tests for git ls-files based discovery."""

    def test_excludes_untracked_directories(self, tmp_path: Path) -> None:
        """Files in untracked dirs that are gitignored should be excluded."""
        tracked_file = tmp_path / "tracked.py"
        tracked_file.write_text("x = 1")

        untracked_dir = tmp_path / "untracked_dir"
        untracked_dir.mkdir()
        (untracked_dir / "module.py").write_text("y = 2")

        # Add .gitignore to exclude the untracked dir
        (tmp_path / ".gitignore").write_text("untracked_dir/\n")

        _git_init_and_add(tmp_path, "tracked.py", ".gitignore")

        config = ProjectConfig()
        result = discover_files(tmp_path, config)

        resolved_tracked = (tmp_path / "tracked.py").resolve()
        resolved_untracked = (tmp_path / "untracked_dir" / "module.py").resolve()
        assert resolved_tracked in result
        assert resolved_untracked not in result

    def test_returns_resolved_absolute_paths(self, tmp_path: Path) -> None:
        """All returned paths must be absolute and resolved."""
        (tmp_path / "app.py").write_text("x = 1")
        _git_init_and_add(tmp_path, "app.py")

        config = ProjectConfig()
        result = discover_files(tmp_path, config)

        assert len(result) >= 1
        for p in result:
            assert p.is_absolute(), f"Path {p} is not absolute"
            assert str(p) == str(p.resolve()), f"Path {p} is not resolved"

    def test_falls_back_to_rglob_outside_git(self, tmp_path: Path) -> None:
        """Discovery should work in a non-git directory via rglob fallback."""
        (tmp_path / "app.py").write_text("x = 1")
        config = ProjectConfig()

        # tmp_path is not a git repo, so git ls-files will fail
        result = discover_files(tmp_path, config)

        resolved = (tmp_path / "app.py").resolve()
        assert resolved in result
