"""Tests for Voyage tokenizer wrapper."""

from clew.chunker.tokenizer import chunk_fits, count_tokens


class TestCountTokens:
    def test_empty_string(self) -> None:
        assert count_tokens("") == 0

    def test_simple_text(self) -> None:
        tokens = count_tokens("hello world")
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_python_code(self) -> None:
        code = "def hello():\n    return 'world'"
        tokens = count_tokens(code)
        assert tokens > 0

    def test_longer_text_has_more_tokens(self) -> None:
        short = count_tokens("hello")
        long = count_tokens("hello world this is a longer sentence")
        assert long > short


class TestChunkFits:
    def test_small_chunk_fits(self) -> None:
        assert chunk_fits("hello world", max_tokens=100) is True

    def test_default_limit(self) -> None:
        assert chunk_fits("x" * 10) is True

    def test_large_chunk_does_not_fit(self) -> None:
        large = "word " * 5000
        assert chunk_fits(large, max_tokens=10) is False
