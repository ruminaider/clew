"""Tests for Python relationship extraction."""

from __future__ import annotations

import pytest

from code_search.chunker.parser import ASTParser
from code_search.indexer.extractors.python import PythonRelationshipExtractor


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


@pytest.fixture
def extractor() -> PythonRelationshipExtractor:
    return PythonRelationshipExtractor()


class TestImportExtraction:
    def test_simple_import(self, extractor: PythonRelationshipExtractor, parser: ASTParser) -> None:
        source = "import os\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        assert any(r.relationship == "imports" and r.target_entity == "os" for r in rels)

    def test_from_import(self, extractor: PythonRelationshipExtractor, parser: ASTParser) -> None:
        source = "from os.path import join, exists\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        assert any(r.relationship == "imports" and r.target_entity == "os.path::join" for r in rels)
        assert any(
            r.relationship == "imports" and r.target_entity == "os.path::exists" for r in rels
        )

    def test_relative_import(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "from .utils import helper\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/views.py")
        assert any(r.relationship == "imports" and "helper" in r.target_entity for r in rels)

    def test_import_source_entity_is_file_module(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "import os\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        import_rels = [r for r in rels if r.relationship == "imports"]
        assert all(r.source_entity == "app/main.py" for r in import_rels)

    def test_import_confidence_is_static(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "import os\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        import_rels = [r for r in rels if r.relationship == "imports"]
        assert all(r.confidence == "static" for r in import_rels)


class TestInheritanceExtraction:
    def test_single_base_class(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "class Foo(Bar):\n    pass\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert any(
            r.relationship == "inherits"
            and r.source_entity == "app/models.py::Foo"
            and r.target_entity == "Bar"
            for r in rels
        )

    def test_multiple_base_classes(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "class Foo(Bar, Baz):\n    pass\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        inherits = [r for r in rels if r.relationship == "inherits"]
        assert len(inherits) == 2

    def test_no_base_class(self, extractor: PythonRelationshipExtractor, parser: ASTParser) -> None:
        source = "class Foo:\n    pass\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert not any(r.relationship == "inherits" for r in rels)

    def test_dotted_base_class(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        """class Foo(models.Model) extracts 'models.Model'."""
        source = "class Foo(models.Model):\n    pass\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert any(r.relationship == "inherits" and r.target_entity == "models.Model" for r in rels)


class TestDecoratorExtraction:
    def test_simple_decorator(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "@login_required\ndef view(request):\n    pass\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/views.py")
        assert any(
            r.relationship == "decorates"
            and r.source_entity == "login_required"
            and r.target_entity == "app/views.py::view"
            for r in rels
        )

    def test_dotted_decorator(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "@app.route('/')\ndef index():\n    pass\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/routes.py")
        assert any(r.relationship == "decorates" and r.source_entity == "app.route" for r in rels)

    def test_class_decorator(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "@dataclass\nclass Foo:\n    x: int\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert any(
            r.relationship == "decorates" and r.target_entity == "app/models.py::Foo" for r in rels
        )


class TestCallExtraction:
    def test_simple_function_call(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "def main():\n    helper()\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        assert any(
            r.relationship == "calls"
            and r.source_entity == "app/main.py::main"
            and r.target_entity == "helper"
            for r in rels
        )

    def test_method_call(self, extractor: PythonRelationshipExtractor, parser: ASTParser) -> None:
        source = "def main():\n    self.save()\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        assert any(r.relationship == "calls" and r.target_entity == "self.save" for r in rels)

    def test_chained_call(self, extractor: PythonRelationshipExtractor, parser: ASTParser) -> None:
        source = "def query():\n    queryset.filter(active=True).order_by('name')\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/views.py")
        calls = [r for r in rels if r.relationship == "calls"]
        assert len(calls) >= 1

    def test_call_confidence_is_inferred(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "def main():\n    helper()\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        call_rels = [r for r in rels if r.relationship == "calls"]
        assert all(r.confidence == "inferred" for r in call_rels)

    def test_call_within_class_method(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "class Foo:\n    def bar(self):\n        baz()\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/models.py")
        assert any(
            r.relationship == "calls"
            and r.source_entity == "app/models.py::Foo.bar"
            and r.target_entity == "baz"
            for r in rels
        )

    def test_no_calls_outside_functions(
        self, extractor: PythonRelationshipExtractor, parser: ASTParser
    ) -> None:
        """Top-level calls (e.g., module-level) use file as source entity."""
        source = "print('hello')\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/main.py")
        assert any(
            r.relationship == "calls"
            and r.source_entity == "app/main.py"
            and r.target_entity == "print"
            for r in rels
        )
