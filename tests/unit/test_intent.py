"""Tests for query intent classification."""

from code_search.search.intent import classify_intent, get_intent_collection_preference
from code_search.search.models import QueryIntent


class TestClassifyIntent:
    def test_debug_keywords(self) -> None:
        assert classify_intent("why does login fail") == QueryIntent.DEBUG
        assert classify_intent("fix the auth bug") == QueryIntent.DEBUG
        assert classify_intent("error in payment") == QueryIntent.DEBUG

    def test_location_keywords(self) -> None:
        assert classify_intent("where is the User model defined") == QueryIntent.LOCATION
        assert classify_intent("find the auth middleware") == QueryIntent.LOCATION

    def test_docs_keywords(self) -> None:
        assert classify_intent("what is the prescription model") == QueryIntent.DOCS
        assert classify_intent("explain the auth flow") == QueryIntent.DOCS

    def test_default_is_code(self) -> None:
        assert classify_intent("user authentication handler") == QueryIntent.CODE

    def test_case_insensitive(self) -> None:
        assert classify_intent("FIX the BUG") == QueryIntent.DEBUG
        assert classify_intent("WHERE is Config") == QueryIntent.LOCATION

    def test_debug_takes_priority(self) -> None:
        assert classify_intent("fix where the error is") == QueryIntent.DEBUG

    def test_empty_query_is_code(self) -> None:
        assert classify_intent("") == QueryIntent.CODE

    def test_code_query(self) -> None:
        assert classify_intent("prescription fill order model") == QueryIntent.CODE


class TestIntentCollectionPreference:
    def test_docs_prefers_docs_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.DOCS) == "docs"

    def test_code_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.CODE) == "code"

    def test_debug_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.DEBUG) == "code"

    def test_location_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.LOCATION) == "code"
