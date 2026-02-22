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


class TestEnumerationAutoDetectionRemoved:
    """ENUMERATION auto-detection was removed (0/45 agent queries matched in V4.1).

    ENUMERATION intent is still available via explicit mode="keyword" override.
    These tests verify that former ENUMERATION queries now classify as their
    natural fallback (CODE, DEBUG, DOCS, or LOCATION).
    """

    def test_find_all_url_patterns_now_location(self) -> None:
        assert classify_intent("find all URL patterns") == QueryIntent.LOCATION

    def test_list_all_models_now_code(self) -> None:
        assert classify_intent("list all models") == QueryIntent.CODE

    def test_every_instance_now_code(self) -> None:
        assert classify_intent("every instance of ValidationError") == QueryIntent.CODE

    def test_all_callers_now_code(self) -> None:
        assert classify_intent("all callers of process_order") == QueryIntent.CODE

    def test_enumerate_api_endpoints_now_code(self) -> None:
        assert classify_intent("enumerate all API endpoints") == QueryIntent.CODE

    def test_all_celery_tasks_now_code(self) -> None:
        assert classify_intent("all Celery tasks") == QueryIntent.CODE

    def test_find_auth_handler_still_location(self) -> None:
        assert classify_intent("find the auth handler") == QueryIntent.LOCATION

    def test_find_all_bugs_still_debug(self) -> None:
        assert classify_intent("find all bugs in auth") == QueryIntent.DEBUG

    def test_how_many_errors_still_debug(self) -> None:
        assert classify_intent("how many errors in production") == QueryIntent.DEBUG

    def test_explain_all_middleware_still_docs(self) -> None:
        assert classify_intent("explain all the middleware") == QueryIntent.DOCS

    def test_handles_all_requests_still_code(self) -> None:
        assert classify_intent("the auth handler handles all requests") == QueryIntent.CODE


class TestExpandedDebugDetection:
    """Tests for expanded DEBUG intent detection (V4.2 fix for E4 false positives)."""

    def test_investigate_triggers_debug_with_question(self) -> None:
        assert classify_intent("why is the payment flow failing?") == QueryIntent.DEBUG

    def test_not_working_phrase(self) -> None:
        assert classify_intent("auth middleware not working") == QueryIntent.DEBUG

    def test_doesnt_work_phrase(self) -> None:
        assert classify_intent("login doesn't work after deploy") == QueryIntent.DEBUG

    def test_issue_with_error_context(self) -> None:
        assert classify_intent("issue with timeout error in API") == QueryIntent.DEBUG

    def test_investigate_with_error_context(self) -> None:
        assert classify_intent("investigate the 500 error on checkout") == QueryIntent.DEBUG

    def test_two_soft_keywords_triggers_debug(self) -> None:
        """Two or more soft keywords trigger DEBUG without needing question/error."""
        assert classify_intent("investigate payment issue") == QueryIntent.DEBUG

    def test_problem_without_error_context_and_question(self) -> None:
        """Single soft keyword needs question form or error context."""
        assert classify_intent("problem with the auth flow") != QueryIntent.DEBUG

    def test_diagnose_with_question(self) -> None:
        assert classify_intent("why does this diagnose step fail?") == QueryIntent.DEBUG


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
