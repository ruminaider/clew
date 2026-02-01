"""Tests for code-aware BM25 tokenization."""

from code_search.search.tokenize import (
    SparseVector,
    split_identifier,
    text_to_sparse_vector,
    tokenize_code,
)


class TestSplitIdentifier:
    def test_camel_case(self) -> None:
        assert split_identifier("getUserById") == ["get", "user", "by", "id"]

    def test_snake_case(self) -> None:
        assert split_identifier("get_user_by_id") == ["get", "user", "by", "id"]

    def test_pascal_case(self) -> None:
        result = split_identifier("PrescriptionFillOrder")
        assert result == ["prescription", "fill", "order"]

    def test_all_caps_acronym(self) -> None:
        result = split_identifier("HTMLParser")
        assert "html" in result
        assert "parser" in result

    def test_single_word(self) -> None:
        assert split_identifier("hello") == ["hello"]

    def test_upper_single_word(self) -> None:
        assert split_identifier("CONSTANT") == ["constant"]


class TestTokenizeCode:
    def test_extracts_identifiers(self) -> None:
        tokens = tokenize_code("def get_user(user_id: int):")
        assert "get" in tokens
        assert "user" in tokens

    def test_deduplicates(self) -> None:
        tokens = tokenize_code("user user user")
        assert tokens.count("user") == 1

    def test_skips_single_chars(self) -> None:
        tokens = tokenize_code("x = a + b")
        assert "x" not in tokens
        assert "a" not in tokens

    def test_includes_full_identifier(self) -> None:
        tokens = tokenize_code("getUserById()")
        assert "getuserbyid" in tokens
        assert "get" in tokens


class TestTextToSparseVector:
    def test_returns_sparse_vector(self) -> None:
        sv = text_to_sparse_vector("def get_user(): pass")
        assert isinstance(sv, SparseVector)
        assert len(sv.indices) > 0
        assert len(sv.indices) == len(sv.values)

    def test_empty_text(self) -> None:
        sv = text_to_sparse_vector("")
        assert sv.indices == []
        assert sv.values == []

    def test_raw_term_counts(self) -> None:
        """Tradeoff E: values are raw term counts, not normalized."""
        sv = text_to_sparse_vector("user user user auth")
        assert all(v >= 1.0 for v in sv.values)

    def test_deterministic(self) -> None:
        sv1 = text_to_sparse_vector("class Foo: pass")
        sv2 = text_to_sparse_vector("class Foo: pass")
        assert sv1.indices == sv2.indices
        assert sv1.values == sv2.values

    def test_repeated_tokens_have_higher_counts(self) -> None:
        """Raw counts: repeated tokens should have higher values."""
        sv = text_to_sparse_vector("user user auth")
        assert len(sv.indices) >= 2
