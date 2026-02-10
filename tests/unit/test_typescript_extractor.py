"""Tests for TypeScript/JavaScript relationship extraction."""

from __future__ import annotations

import pytest

from clew.chunker.parser import ASTParser
from clew.indexer.extractors.typescript import TypeScriptRelationshipExtractor


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


@pytest.fixture
def extractor() -> TypeScriptRelationshipExtractor:
    return TypeScriptRelationshipExtractor()


class TestImportExtraction:
    def test_named_import(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "import { Foo, Bar } from './models';\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/app.ts")
        assert any(r.relationship == "imports" and r.target_entity == "./models::Foo" for r in rels)
        assert any(r.relationship == "imports" and r.target_entity == "./models::Bar" for r in rels)

    def test_default_import(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "import React from 'react';\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/app.ts")
        assert any(r.relationship == "imports" and r.target_entity == "react::React" for r in rels)

    def test_namespace_import(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "import * as path from 'path';\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/app.ts")
        assert any(r.relationship == "imports" and r.target_entity == "path" for r in rels)

    def test_import_source_entity_is_file(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "import { Foo } from './bar';\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/app.ts")
        assert all(r.source_entity == "src/app.ts" for r in rels)

    def test_require_import(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        """CommonJS require is also captured."""
        source = "const fs = require('fs');\n"
        tree = parser.parse(source, "javascript")
        rels = extractor.extract(tree, source, "src/app.js")
        assert any(r.relationship == "imports" and r.target_entity == "fs" for r in rels)


class TestInheritanceExtraction:
    def test_extends_class(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "class Foo extends Bar {\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/models.ts")
        assert any(
            r.relationship == "inherits"
            and r.source_entity == "src/models.ts::Foo"
            and r.target_entity == "Bar"
            for r in rels
        )

    def test_no_inheritance(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "class Foo {\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/models.ts")
        assert not any(r.relationship == "inherits" for r in rels)


class TestJSXRenderExtraction:
    def test_jsx_self_closing(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "function App() {\n  return <Header />;\n}\n"
        tree = parser.parse(source, "tsx")
        rels = extractor.extract(tree, source, "src/App.tsx")
        assert any(
            r.relationship == "renders"
            and r.source_entity == "src/App.tsx::App"
            and r.target_entity == "Header"
            for r in rels
        )

    def test_jsx_with_children(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "function Page() {\n  return <Layout><Content /></Layout>;\n}\n"
        tree = parser.parse(source, "tsx")
        rels = extractor.extract(tree, source, "src/Page.tsx")
        renders = [r for r in rels if r.relationship == "renders"]
        target_names = {r.target_entity for r in renders}
        assert "Layout" in target_names
        assert "Content" in target_names

    def test_html_elements_ignored(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        """Lowercase JSX elements (div, span) are HTML, not components."""
        source = "function App() {\n  return <div><span>hi</span></div>;\n}\n"
        tree = parser.parse(source, "tsx")
        rels = extractor.extract(tree, source, "src/App.tsx")
        renders = [r for r in rels if r.relationship == "renders"]
        assert len(renders) == 0


class TestCallExtraction:
    def test_simple_function_call(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "function main() {\n  helper();\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/app.ts")
        assert any(r.relationship == "calls" and r.target_entity == "helper" for r in rels)

    def test_method_call(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "function main() {\n  service.process();\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/app.ts")
        assert any(r.relationship == "calls" and r.target_entity == "service.process" for r in rels)


class TestAPICallExtraction:
    def test_fetch_call(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "async function getUsers() {\n  const r = await fetch('/api/users');\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/api.ts")
        assert any(
            r.relationship == "calls_api"
            and r.target_entity == "/api/users"
            and r.confidence == "inferred"
            for r in rels
        )

    def test_fetch_with_template_literal_skipped(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        """Template literals can't be statically resolved -- skip them."""
        source = "async function get(id) {\n  await fetch(`/api/users/${id}`);\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/api.ts")
        api_rels = [r for r in rels if r.relationship == "calls_api"]
        assert len(api_rels) == 0

    def test_axios_get(self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser) -> None:
        source = "async function getUsers() {\n  await axios.get('/api/users');\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/api.ts")
        assert any(r.relationship == "calls_api" and r.target_entity == "/api/users" for r in rels)

    def test_axios_post(
        self, extractor: TypeScriptRelationshipExtractor, parser: ASTParser
    ) -> None:
        source = "async function create() {\n  await axios.post('/api/items', data);\n}\n"
        tree = parser.parse(source, "typescript")
        rels = extractor.extract(tree, source, "src/api.ts")
        assert any(r.relationship == "calls_api" and r.target_entity == "/api/items" for r in rels)
