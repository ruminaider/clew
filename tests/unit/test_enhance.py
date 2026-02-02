"""Tests for query enhancement with terminology expansion."""

from pathlib import Path

from code_search.search.enhance import QueryEnhancer, should_skip_enhancement


class TestShouldSkipEnhancement:
    def test_quoted_query(self) -> None:
        assert should_skip_enhancement('"exact match"') is True

    def test_pascal_case_identifier(self) -> None:
        assert should_skip_enhancement("PrescriptionFillOrder") is True

    def test_snake_case_identifier(self) -> None:
        assert should_skip_enhancement("get_user_by_id") is True

    def test_file_path(self) -> None:
        assert should_skip_enhancement("src/models.py") is True
        assert should_skip_enhancement("components/Auth.tsx") is True

    def test_normal_query_not_skipped(self) -> None:
        assert should_skip_enhancement("how does auth work") is False

    def test_single_word_not_skipped(self) -> None:
        assert should_skip_enhancement("authentication") is False


class TestQueryEnhancerAbbreviations:
    def test_no_terminology_file(self) -> None:
        enhancer = QueryEnhancer()
        assert enhancer.enhance("hello world") == "hello world"

    def test_with_abbreviations(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text(
            "abbreviations:\n  BV: bacterial vaginosis\n  UTI: urinary tract infection\n"
        )
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("BV treatment")
        assert "bacterial vaginosis" in result
        assert "BV" in result

    def test_skipped_query_unchanged(self) -> None:
        enhancer = QueryEnhancer()
        assert enhancer.enhance('"exact search"') == '"exact search"'

    def test_non_matching_unchanged(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text("abbreviations:\n  BV: bacterial vaginosis\n")
        enhancer = QueryEnhancer(terminology_file=term_file)
        assert enhancer.enhance("prescription model") == "prescription model"

    def test_missing_file_no_error(self) -> None:
        enhancer = QueryEnhancer(terminology_file=Path("/nonexistent/file.yaml"))
        assert enhancer.enhance("test query") == "test query"

    def test_case_insensitive_expansion(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text("abbreviations:\n  bv: bacterial vaginosis\n")
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("bv treatment")
        assert "bacterial vaginosis" in result


class TestQueryEnhancerSynonyms:
    def test_synonym_expansion(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text(
            "synonyms:\n  consult:\n    - consultation\n    - telehealth\n    - wheel\n"
        )
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("consult flow")
        assert "consultation" in result or "telehealth" in result

    def test_synonym_and_abbreviation_together(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text(
            "abbreviations:\n  BV: bacterial vaginosis\n"
            "synonyms:\n  consult:\n    - consultation\n    - telehealth\n"
        )
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("BV consult")
        assert "bacterial vaginosis" in result
        assert "consultation" in result or "telehealth" in result

    def test_empty_synonyms_section(self, tmp_path: Path) -> None:
        term_file = tmp_path / "terminology.yaml"
        term_file.write_text("abbreviations:\n  BV: bacterial vaginosis\nsynonyms: {}\n")
        enhancer = QueryEnhancer(terminology_file=term_file)
        result = enhancer.enhance("BV treatment")
        assert "bacterial vaginosis" in result
