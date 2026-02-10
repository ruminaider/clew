"""Tests for docstring extraction from AST nodes."""

import pytest

from clew.chunker.parser import ASTParser
from clew.chunker.strategies import PythonChunker


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


@pytest.fixture
def python_chunker() -> PythonChunker:
    return PythonChunker()


class TestDocstringExtraction:
    """Test docstring extraction from AST nodes."""

    def test_function_with_docstring(
        self, python_chunker: PythonChunker, parser: ASTParser
    ) -> None:
        source = '''def greet(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}"
'''
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        assert len(entities) == 1
        assert entities[0].docstring == "Say hello to someone."

    def test_function_without_docstring(
        self, python_chunker: PythonChunker, parser: ASTParser
    ) -> None:
        source = """def add(a, b):
    return a + b
"""
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        assert len(entities) == 1
        assert entities[0].docstring is None

    def test_class_with_docstring(self, python_chunker: PythonChunker, parser: ASTParser) -> None:
        source = '''class User:
    """Represents a user account."""
    name: str
'''
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        assert len(entities) == 1
        assert entities[0].docstring == "Represents a user account."

    def test_method_with_multiline_docstring(
        self, python_chunker: PythonChunker, parser: ASTParser
    ) -> None:
        source = '''class Calculator:
    def multiply(self, a, b):
        """Multiply two numbers.

        Args:
            a: First number.
            b: Second number.
        """
        return a * b
'''
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        method = [e for e in entities if e.entity_type == "method"][0]
        assert method.docstring is not None
        assert method.docstring.startswith("Multiply two numbers.")

    def test_function_with_string_literal_not_docstring(
        self, python_chunker: PythonChunker, parser: ASTParser
    ) -> None:
        source = """def example():
    x = "not a docstring"
    return x
"""
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        assert entities[0].docstring is None

    def test_function_with_rstring_docstring(
        self, python_chunker: PythonChunker, parser: ASTParser
    ) -> None:
        source = '''def regex_helper():
    r"""Match email pattern."""
    pass
'''
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        assert entities[0].docstring == "Match email pattern."

    def test_function_with_fstring_not_docstring(
        self, python_chunker: PythonChunker, parser: ASTParser
    ) -> None:
        source = '''def greeting():
    f"""Hello {name}"""
    pass
'''
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        assert entities[0].docstring is None

    def test_function_with_bstring_not_docstring(
        self, python_chunker: PythonChunker, parser: ASTParser
    ) -> None:
        source = '''def binary():
    b"""Not a docstring"""
    pass
'''
        tree = parser.parse(source, "python")
        entities = list(python_chunker.extract_entities(tree, source))
        assert entities[0].docstring is None
