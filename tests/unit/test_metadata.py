"""Tests for metadata extraction: app_name, layer, signature, chunk_id."""

import hashlib

from clew.indexer.metadata import (
    build_chunk_id,
    classify_layer,
    detect_app_name,
    extract_signature,
)


class TestClassifyLayer:
    def test_models_py(self) -> None:
        assert classify_layer("backend/care/models.py") == "model"

    def test_views_py(self) -> None:
        assert classify_layer("backend/care/views.py") == "view"

    def test_viewsets_py(self) -> None:
        assert classify_layer("backend/care/viewsets.py") == "view"

    def test_serializers_py(self) -> None:
        assert classify_layer("backend/care/serializers.py") == "serializer"

    def test_tasks_py(self) -> None:
        assert classify_layer("backend/care/tasks.py") == "task"

    def test_service_py(self) -> None:
        assert classify_layer("backend/care/service.py") == "service"

    def test_services_py(self) -> None:
        assert classify_layer("backend/care/services.py") == "service"

    def test_tsx_component(self) -> None:
        assert classify_layer("frontend/components/Auth.tsx") == "component"

    def test_jsx_component(self) -> None:
        assert classify_layer("frontend/components/Auth.jsx") == "component"

    def test_utils_fallback_other(self) -> None:
        """Tradeoff C: unmatched files get 'other' layer."""
        assert classify_layer("backend/care/utils.py") == "other"

    def test_admin_fallback_other(self) -> None:
        assert classify_layer("backend/care/admin.py") == "other"

    def test_unknown_extension(self) -> None:
        assert classify_layer("data.csv") == "other"

    def test_init_py(self) -> None:
        assert classify_layer("backend/care/__init__.py") == "other"


class TestDetectAppName:
    def test_django_models(self) -> None:
        assert detect_app_name("backend/care/models.py") == "care"

    def test_django_views(self) -> None:
        assert detect_app_name("backend/consults/views.py") == "consults"

    def test_nested_path(self) -> None:
        assert detect_app_name("backend/consults/wheel/wheel.py") == "wheel"

    def test_simple_file(self) -> None:
        assert detect_app_name("utils.py") == ""

    def test_frontend_component(self) -> None:
        assert detect_app_name("frontend/components/Auth.tsx") == "components"

    def test_deep_nested(self) -> None:
        assert detect_app_name("backend/care/tests/test_models.py") == "tests"


class TestExtractSignature:
    def test_function(self) -> None:
        code = "def is_expired(self) -> bool:\n    return True"
        assert extract_signature("method", code) == "def is_expired(self) -> bool"

    def test_class(self) -> None:
        code = "class Prescription(BaseModel):\n    pass"
        assert extract_signature("class", code) == "class Prescription(BaseModel)"

    def test_async_function(self) -> None:
        code = "async def fetch_data(url: str) -> dict:\n    pass"
        assert extract_signature("function", code) == "async def fetch_data(url: str) -> dict"

    def test_section_returns_empty(self) -> None:
        code = "# Some comment\nx = 1"
        assert extract_signature("section", code) == ""

    def test_empty_content(self) -> None:
        assert extract_signature("function", "") == ""


class TestBuildChunkId:
    def test_named_entity(self) -> None:
        chunk_id = build_chunk_id(
            "backend/care/models.py",
            "method",
            "Prescription.is_expired",
        )
        assert chunk_id == "backend/care/models.py::method::Prescription.is_expired"

    def test_function(self) -> None:
        chunk_id = build_chunk_id("src/utils.py", "function", "helper")
        assert chunk_id == "src/utils.py::function::helper"

    def test_class(self) -> None:
        chunk_id = build_chunk_id("models.py", "class", "User")
        assert chunk_id == "models.py::class::User"

    def test_toplevel_fallback(self) -> None:
        content = "x = 1\ny = 2"
        chunk_id = build_chunk_id("main.py", "section", "", content=content)
        expected_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        assert chunk_id == f"main.py::toplevel::{expected_hash}"

    def test_toplevel_no_name(self) -> None:
        chunk_id = build_chunk_id("main.py", "toplevel", "", content="some code")
        assert chunk_id.startswith("main.py::toplevel::")
        assert len(chunk_id.split("::")[-1]) == 12
