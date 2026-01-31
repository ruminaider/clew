"""Tests for the three-tier splitter fallback chain."""

from code_search.chunker.fallback import (
    line_split,
    split_file,
    token_recursive_split,
)
from code_search.chunker.parser import ASTParser
from code_search.chunker.tokenizer import count_tokens


class TestTokenRecursiveSplit:
    def test_small_text_returns_single_chunk(self) -> None:
        result = token_recursive_split("hello world", max_tokens=100)
        assert len(result) == 1
        assert result[0] == "hello world"

    def test_splits_on_paragraph_boundaries(self) -> None:
        text = "\n\n".join(["paragraph " + "word " * 20 for _ in range(3)])
        result = token_recursive_split(text, max_tokens=20, overlap_tokens=0)
        assert len(result) >= 2
        for chunk in result:
            assert count_tokens(chunk) <= 20

    def test_all_chunks_within_limit(self) -> None:
        text = "word " * 500
        result = token_recursive_split(text, max_tokens=50, overlap_tokens=0)
        for chunk in result:
            assert count_tokens(chunk) <= 50

    def test_overlap_applied(self) -> None:
        text = "\n\n".join([f"Section {i}: " + "content " * 50 for i in range(5)])
        result = token_recursive_split(text, max_tokens=100, overlap_tokens=20)
        assert len(result) >= 2


class TestLineSplit:
    def test_small_text_returns_single_chunk(self) -> None:
        result = line_split("hello", max_tokens=100)
        assert len(result) == 1

    def test_splits_by_lines(self) -> None:
        text = "\n".join(["line " * 20] * 10)
        result = line_split(text, max_tokens=50, overlap_tokens=0)
        assert len(result) >= 2
        for chunk in result:
            assert count_tokens(chunk) <= 50


class TestSplitFile:
    def setup_method(self) -> None:
        self.parser = ASTParser()

    def test_valid_python_uses_ast(self, sample_python_file: str) -> None:
        chunks = split_file(
            "models.py", sample_python_file, max_tokens=3000, ast_parser=self.parser
        )
        assert len(chunks) > 0
        assert all(c.source == "ast" for c in chunks)

    def test_plain_text_uses_fallback(self) -> None:
        plain = "This is just plain text.\n" * 100
        chunks = split_file("readme.txt", plain, max_tokens=50, ast_parser=self.parser)
        assert len(chunks) > 0
        assert all(c.source == "fallback" for c in chunks)

    def test_all_chunks_within_token_limit(self) -> None:
        plain = "word " * 2000
        chunks = split_file("big.txt", plain, max_tokens=100, ast_parser=self.parser)
        for chunk in chunks:
            assert count_tokens(chunk.content) <= 100
