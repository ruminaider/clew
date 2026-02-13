# clewdex

Semantic code search with hybrid retrieval and MCP integration for [Claude Code](https://claude.com/claude-code).

This is an npm wrapper for the [clewdex](https://github.com/ruminaider/clew) Python package. It delegates to the locally installed `clew` CLI or falls back to `pipx run`.

## Install

The recommended way to install clewdex is via pip or pipx:

```bash
pip install clewdex
# or
pipx install clewdex
```

Then use `npx clewdex` as an alias, or just use `clew` directly.

## What is clewdex?

clewdex is the semantic code indexer from [clew](https://github.com/ruminaider/clew). It indexes your codebase with AST-aware chunking, embeds it with Voyage AI, stores it in Qdrant, and serves results through both a CLI and an MCP server that Claude Code can call directly.

- **Hybrid search** — Dense embeddings + BM25 fused with Reciprocal Rank Fusion
- **AST-aware chunking** — tree-sitter parses Python, TypeScript, and JavaScript
- **Code relationship tracing** — imports, calls, inheritance, decorators, and more
- **MCP integration** — Claude Code can search your codebase directly

See the full documentation at [github.com/ruminaider/clew](https://github.com/ruminaider/clew).
