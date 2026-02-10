"""Tests for test file relationship detection."""

from __future__ import annotations

import pytest

from code_search.chunker.parser import ASTParser
from code_search.indexer.extractors.tests import TestRelationshipExtractor


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


@pytest.fixture
def extractor() -> TestRelationshipExtractor:
    return TestRelationshipExtractor()


class TestTestDetection:
    def test_python_test_importing_module(
        self, extractor: TestRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "from app.models import User\n\ndef test_user():\n    pass\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "tests/test_models.py")
        assert any(
            r.relationship == "tests"
            and r.source_entity == "tests/test_models.py"
            and "User" in r.target_entity
            for r in rels
        )

    def test_non_test_file_ignored(
        self, extractor: TestRelationshipExtractor, parser: ASTParser
    ) -> None:
        """Regular files don't get 'tests' relationships even with imports."""
        source = "from app.models import User\n"
        tree = parser.parse(source, "python")
        rels = extractor.extract(tree, source, "app/views.py")
        assert not any(r.relationship == "tests" for r in rels)

    def test_typescript_test_file(
        self, extractor: TestRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = (
            "import { UserService } from '../services/user';\n\ntest('creates user', () => {});\n"
        )
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/__tests__/user.test.ts")
        assert any(r.relationship == "tests" and "UserService" in r.target_entity for r in rels)

    def test_spec_file_detected(
        self, extractor: TestRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "import { render } from '@testing-library/react';\nimport App from '../App';\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/App.spec.tsx")
        assert any(r.relationship == "tests" for r in rels)
