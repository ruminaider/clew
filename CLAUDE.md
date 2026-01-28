# code-search

Semantic code search tool with hybrid retrieval and MCP integration for Claude Code.

## Project State

**Documentation only — no implementation code exists yet.** All design is complete and ready to build.

## Key Files

- `docs/DESIGN.md` — Architecture, chunking strategy, search pipeline, MCP tools, metadata schema, project structure
- `docs/IMPLEMENTATION.md` — Concrete specs: repo structure, dependencies, SQLite schemas, Pydantic models, tree-sitter setup, error handling, testing strategy, phase tasks with acceptance criteria
- `docs/adr/` — Architecture Decision Records (Qdrant over Milvus, build vs adopt claude-context, ported features)
- `docs/plans/2026-02-06-three-layer-knowledge-design.md` — Future roadmap (V1.2+), not V1 scope

## Tech Stack

- Python >=3.10, Qdrant (Docker), Voyage AI voyage-code-3, tree-sitter, typer + rich CLI, Pydantic v2, SQLite for caching
- Testing: pytest + pytest-asyncio, respx for HTTP mocking
- Linting: ruff, mypy (strict)

## Build Order

Phase 1 (Core Infrastructure) → Phase 2 (Search Pipeline) → Phase 3 (MCP Integration) → Phase 4 (Polish & Evaluation)

## Conventions

- Use `ruff` for formatting and linting
- Use `mypy --strict` for type checking
- Async where interacting with Voyage API or Qdrant
- All config through Pydantic models validated from YAML
- Error messages should tell the user how to fix the problem (e.g., "Qdrant not running. Start with: docker compose up -d qdrant")
