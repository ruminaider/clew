"""Tests for AST parsing and entity extraction."""

from code_search.chunker.parser import ASTParser
from code_search.chunker.strategies import PythonChunker


class TestASTParser:
    def setup_method(self) -> None:
        self.parser = ASTParser()

    def test_get_language_python(self) -> None:
        assert self.parser.get_language("models.py") == "python"

    def test_get_language_typescript(self) -> None:
        assert self.parser.get_language("app.ts") == "typescript"

    def test_get_language_tsx(self) -> None:
        assert self.parser.get_language("Component.tsx") == "tsx"

    def test_get_language_javascript(self) -> None:
        assert self.parser.get_language("index.js") == "javascript"

    def test_get_language_jsx(self) -> None:
        assert self.parser.get_language("App.jsx") == "javascript"

    def test_get_language_unsupported(self) -> None:
        assert self.parser.get_language("style.css") is None

    def test_parse_valid_python(self) -> None:
        code = "def hello():\n    return 'world'"
        tree = self.parser.parse(code, "python")
        assert tree is not None
        assert tree.root_node is not None

    def test_parse_file_auto_detect(self) -> None:
        code = "class Foo:\n    pass"
        tree = self.parser.parse_file("test.py", code)
        assert tree is not None

    def test_parse_file_unsupported_returns_none(self) -> None:
        assert self.parser.parse_file("style.css", "body {}") is None


class TestPythonChunker:
    def setup_method(self) -> None:
        self.parser = ASTParser()
        self.chunker = PythonChunker()

    def test_extract_function(self) -> None:
        code = "def greet(name: str) -> str:\n    return f'Hello {name}'"
        tree = self.parser.parse(code, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, code))
        assert len(entities) == 1
        assert entities[0].entity_type == "function"
        assert entities[0].name == "greet"
        assert entities[0].qualified_name == "greet"

    def test_extract_class_and_methods(self, sample_python_file: str) -> None:
        tree = self.parser.parse(sample_python_file, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, sample_python_file))

        names = [e.name for e in entities]
        assert "Prescription" in names
        assert "is_expired" in names
        assert "create_prescription" in names

    def test_method_has_parent_class(self, sample_python_file: str) -> None:
        tree = self.parser.parse(sample_python_file, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, sample_python_file))

        method = next(e for e in entities if e.name == "is_expired")
        assert method.parent_class == "Prescription"
        assert method.qualified_name == "Prescription.is_expired"

    def test_entity_has_line_numbers(self, sample_python_file: str) -> None:
        tree = self.parser.parse(sample_python_file, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, sample_python_file))

        for entity in entities:
            assert entity.line_start > 0
            assert entity.line_end >= entity.line_start

    def test_entity_content_is_source_code(self) -> None:
        code = "def add(a, b):\n    return a + b"
        tree = self.parser.parse(code, "python")
        assert tree is not None
        entities = list(self.chunker.extract_entities(tree, code))
        assert len(entities) == 1
        assert "return a + b" in entities[0].content
