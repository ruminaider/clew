"""Tests for Environment in config.py."""

import importlib
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestEnvironmentAnthropicApiKey:
    def test_environment_anthropic_api_key(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}):
            import code_search.config as config_module

            importlib.reload(config_module)
            env = config_module.Environment()
            assert env.ANTHROPIC_API_KEY == "test-key-123"

    def test_environment_anthropic_api_key_default(self) -> None:
        env_copy = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env_copy, clear=True):
            import code_search.config as config_module

            importlib.reload(config_module)
            env = config_module.Environment()
            assert isinstance(env.ANTHROPIC_API_KEY, str)
            assert env.ANTHROPIC_API_KEY == ""


class TestResolveCacheDir:
    """Test _resolve_cache_dir() resolution order."""

    def test_env_var_takes_priority(self) -> None:
        """CODE_SEARCH_CACHE_DIR env var overrides all other resolution."""
        with patch.dict(os.environ, {"CODE_SEARCH_CACHE_DIR": "/tmp/custom-cache"}):
            from code_search.config import _resolve_cache_dir

            result = _resolve_cache_dir()
            assert result == Path("/tmp/custom-cache")

    def test_git_root_used_when_no_env_var(self) -> None:
        """Falls back to {git_root}/.code-search/ when no env var set."""
        env_copy = {k: v for k, v in os.environ.items() if k != "CODE_SEARCH_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("code_search.config.subprocess") as mock_subprocess:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "/Users/me/myproject\n"
                mock_subprocess.run.return_value = mock_result

                from code_search.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path("/Users/me/myproject/.code-search")

    def test_cwd_fallback_when_not_in_git_repo(self) -> None:
        """Falls back to CWD-relative .code-search/ when not in a git repo."""
        env_copy = {k: v for k, v in os.environ.items() if k != "CODE_SEARCH_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("code_search.config.subprocess") as mock_subprocess:
                mock_result = MagicMock()
                mock_result.returncode = 128
                mock_result.stdout = ""
                mock_subprocess.run.return_value = mock_result

                from code_search.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path(".code-search")

    def test_cwd_fallback_when_git_not_installed(self) -> None:
        """Falls back to CWD-relative .code-search/ when git is not installed."""
        env_copy = {k: v for k, v in os.environ.items() if k != "CODE_SEARCH_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("code_search.config.subprocess") as mock_subprocess:
                mock_subprocess.run.side_effect = FileNotFoundError("git not found")

                from code_search.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path(".code-search")

    def test_cwd_fallback_when_git_times_out(self) -> None:
        """Falls back to CWD-relative .code-search/ when git times out."""
        import subprocess as real_subprocess

        env_copy = {k: v for k, v in os.environ.items() if k != "CODE_SEARCH_CACHE_DIR"}
        with patch.dict(os.environ, env_copy, clear=True):
            with patch("code_search.config.subprocess") as mock_subprocess:
                mock_subprocess.run.side_effect = real_subprocess.TimeoutExpired(
                    cmd="git", timeout=5
                )
                mock_subprocess.TimeoutExpired = real_subprocess.TimeoutExpired

                from code_search.config import _resolve_cache_dir

                result = _resolve_cache_dir()
                assert result == Path(".code-search")
