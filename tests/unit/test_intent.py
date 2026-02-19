"""Tests for query intent classification."""

from clew.search.intent import classify_intent, get_intent_collection_preference
from clew.search.models import QueryIntent


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

    def test_leading_underscore_snake_case_is_location(self) -> None:
        """Bare identifiers with leading underscore should be LOCATION (V2 fix)."""
        assert classify_intent("_process_shopify_order_impl") == QueryIntent.LOCATION

    def test_pascal_case_is_location(self) -> None:
        assert classify_intent("PrescriptionFill") == QueryIntent.LOCATION

    def test_natural_language_not_location(self) -> None:
        """Natural language with spaces should not match as bare identifier."""
        assert classify_intent("how does order processing work") != QueryIntent.LOCATION


class TestEnumerationIntent:
    """Tests for ENUMERATION intent classification (Decision 10A: false-positive suite)."""

    # True positives
    def test_find_all_url_patterns(self) -> None:
        assert classify_intent("find all URL patterns") == QueryIntent.ENUMERATION

    def test_list_all_models(self) -> None:
        assert classify_intent("list all models") == QueryIntent.ENUMERATION

    def test_every_instance_of_error_class(self) -> None:
        assert classify_intent("every instance of ValidationError") == QueryIntent.ENUMERATION

    def test_all_callers_of_function(self) -> None:
        assert classify_intent("all callers of process_order") == QueryIntent.ENUMERATION

    def test_enumerate_api_endpoints(self) -> None:
        assert classify_intent("enumerate all API endpoints") == QueryIntent.ENUMERATION

    def test_count_all_models(self) -> None:
        assert classify_intent("count all models") == QueryIntent.ENUMERATION

    def test_all_references_to_user(self) -> None:
        assert classify_intent("all references to User model") == QueryIntent.ENUMERATION

    def test_how_many_views(self) -> None:
        assert classify_intent("how many views are there") == QueryIntent.ENUMERATION

    def test_all_uses_of_decorator(self) -> None:
        assert classify_intent("all uses of @login_required") == QueryIntent.ENUMERATION

    def test_all_instances_of_class(self) -> None:
        assert classify_intent("all instances of Order class") == QueryIntent.ENUMERATION

    # False positives (should NOT be ENUMERATION)
    def test_find_auth_handler_is_location(self) -> None:
        assert classify_intent("find the auth handler") == QueryIntent.LOCATION

    def test_find_all_bugs_is_debug(self) -> None:
        """DEBUG > ENUMERATION priority."""
        assert classify_intent("find all bugs in auth") == QueryIntent.DEBUG

    def test_how_many_errors_is_debug(self) -> None:
        """DEBUG > ENUMERATION because 'error' is hard DEBUG keyword."""
        assert classify_intent("how many errors in production") == QueryIntent.DEBUG

    def test_explain_all_middleware_is_docs(self) -> None:
        assert classify_intent("explain all the middleware") == QueryIntent.DOCS

    def test_handles_all_requests_is_code(self) -> None:
        """'all' without enumeration phrase prefix is NOT ENUMERATION."""
        assert classify_intent("the auth handler handles all requests") == QueryIntent.CODE

    def test_list_all_documentation_is_docs(self) -> None:
        """'documentation' matches DOCS phrase, DOCS wins over ENUMERATION."""
        assert classify_intent("list all documentation files") == QueryIntent.DOCS

    def test_find_all_endpoints_is_enumeration(self) -> None:
        assert classify_intent("find all API endpoints") == QueryIntent.ENUMERATION


class TestIntentCollectionPreference:
    def test_docs_prefers_docs_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.DOCS) == "docs"

    def test_code_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.CODE) == "code"

    def test_debug_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.DEBUG) == "code"

    def test_location_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.LOCATION) == "code"

    def test_enumeration_prefers_code_collection(self) -> None:
        assert get_intent_collection_preference(QueryIntent.ENUMERATION) == "code"
