"""Tests for Environment in config.py."""

import importlib
import os
from unittest.mock import patch


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
