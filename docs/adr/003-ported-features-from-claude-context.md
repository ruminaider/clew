# ADR-003: Ported Features from claude-context

**Status:** Accepted
**Date:** 2026-02-05
**Deciders:** Engineering team
**Related:** [ADR-002](./002-build-vs-adopt-claude-context.md), [CLAUDE_CONTEXT_ANALYSIS.md](../CLAUDE_CONTEXT_ANALYSIS.md), [DESIGN.md](../DESIGN.md), [IMPLEMENTATION.md](../IMPLEMENTATION.md)

---

## Context

After deciding to build clew as a standalone system ([ADR-002](./002-build-vs-adopt-claude-context.md)), we identified 8 patterns from [claude-context](https://github.com/zilliztech/claude-context) worth porting. These are proven approaches that solve real problems in code indexing systems, adapted to fit our Python/Qdrant stack.

## Decision

Port the following 8 features from claude-context, each adapted to our architecture.

## Ported Features

### 1. AST Fallback Chain

**claude-context approach:** tree-sitter → LangChain RecursiveCharacterTextSplitter → generic line splitter. Uses LangChain as the intermediate fallback for files where tree-sitter fails.

**Our adaptation:** tree-sitter → token-based recursive splitter → line split. We eliminate the LangChain dependency by implementing a lightweight recursive splitter (~100 lines) that splits on token boundaries rather than character boundaries.

**Rationale:** LangChain's text splitter is character-based, not token-aware, which can produce chunks that exceed embedding model limits. Our token-recursive splitter respects Voyage's tokenizer directly. Additionally, LangChain is a heavy dependency (~50+ transitive packages) for a single text-splitting function.

**Implementation:** `clew/chunker/fallback.py` — See [IMPLEMENTATION.md](../IMPLEMENTATION.md)

### 2. Change Detection (Hybrid Strategy)

**claude-context approach:** Merkle DAG built from file content hashes. The standalone tool maintains its own tree structure to detect changes without requiring git.

**Our adaptation:** git-diff as PRIMARY change detection + file-hash as SECONDARY fallback. Git diff is used for incremental updates (fast, accurate), while file hashing serves as a safety net for cases where git history is unreliable (shallow clones, squashed merges, force pushes).

**Rationale:** Our target deployment always has git available (it's a developer tool for git repositories). Git diff is faster and more informative than computing a full Merkle DAG (provides add/modify/delete/rename classification). The file-hash fallback from claude-context's approach is valuable for edge cases.

**Implementation:** `clew/indexer/git.py` (primary), `clew/indexer/file_hash.py` (secondary) — See [DESIGN.md Section 5](../DESIGN.md)

### 3. Batch Embedding with Progress

**claude-context approach:** Sends embeddings in batches of 100 chunks with callback-based progress reporting.

**Our adaptation:** Configurable batch size (default 100) with `rich` progress bars showing chunks processed, tokens embedded, and estimated time remaining.

**Rationale:** The batch size of 100 is well-tested in claude-context and balances API throughput with memory usage. We replace callbacks with rich progress bars for better developer experience in a CLI tool.

**Implementation:** `clew/indexer/batch.py` — See [IMPLEMENTATION.md](../IMPLEMENTATION.md)

### 4. Embedding Provider Abstraction

**claude-context approach:** Multi-provider interface supporting different embedding backends (OpenAI, local models).

**Our adaptation:** Python ABC (`EmbeddingProvider`) defaulting to Voyage AI, with optional OpenAI and Ollama providers. The abstraction exposes `embed()`, `embed_query()`, `dimensions`, and `model_name`.

**Rationale:** While Voyage AI is our primary choice, the abstraction allows:
- Testing with cheaper/faster models during development
- Fallback to OpenAI if Voyage has availability issues
- Local-only indexing with Ollama for air-gapped environments
- Future provider changes without refactoring

**Implementation:** `clew/clients/base.py` — See [IMPLEMENTATION.md](../IMPLEMENTATION.md)

### 5. Chunk Overlap (Non-AST Only)

**claude-context approach:** 300 characters of overlap from the previous chunk prepended to each subsequent chunk.

**Our adaptation:** 200 tokens of overlap, applied ONLY to non-AST fallback chunks. AST-parsed chunks (functions, classes, methods) are self-contained semantic units that should not overlap.

**Rationale:** claude-context applies overlap universally. This can cause a method's context to bleed into the next method's chunk, degrading search precision. By limiting overlap to fallback-split chunks (where we've lost semantic boundaries), we maintain clean chunk boundaries for the common case while improving continuity for the uncommon case.

**Implementation:** `clew/chunker/fallback.py` — See [DESIGN.md Section 3](../DESIGN.md)

### 6. Ignore Pattern Hierarchy

**claude-context approach:** 5-level hierarchy of ignore patterns (defaults, project, directory, file, runtime).

**Our adaptation:** 5-source merge hierarchy with different sources:
1. Built-in defaults (common non-code files)
2. `.gitignore` patterns (already maintained by developers)
3. `.clewignore` (project-specific overrides)
4. `config.yaml` exclude patterns (per-collection configuration)
5. `CLEW_EXCLUDE` environment variable (runtime overrides)

Uses the `pathspec` library for `.gitignore`-compatible pattern matching.

**Rationale:** claude-context's hierarchy is sensible but uses its own pattern format. We align with `.gitignore` syntax (which developers already know) and integrate with the project config system. The env var level enables CI/CD customization without config changes.

**Implementation:** `clew/indexer/ignore.py` — See [IMPLEMENTATION.md](../IMPLEMENTATION.md)

### 7. Dual Chunk ID Strategy

**claude-context approach:** SHA256 hash of `path:start_offset:end_offset:content` for all chunks. This means any change to surrounding code (that shifts offsets) invalidates chunk IDs.

**Our adaptation:** Dual strategy:
- **Entity-based IDs** for named code: `{file_path}::{entity_type}::{qualified_name}` (e.g., `models.py::method::Prescription.is_expired`)
- **Content-hash IDs** for anonymous/top-level code: `{file_path}::toplevel::{sha256(content)[:12]}`

**Rationale:** Entity-based IDs are stable across content changes (adding a docstring doesn't invalidate the chunk ID — only the content hash triggers re-embedding). This is superior to claude-context's offset-based approach, which invalidates chunks when unrelated code above them changes. The content-hash fallback handles code that lacks named entities.

**Implementation:** `clew/chunker/identity.py` — See [DESIGN.md Section 3](../DESIGN.md)

### 8. Safety Limits

**claude-context approach:** Hard limit of 450,000 chunks to prevent runaway indexing.

**Our adaptation:** Configurable multi-level safety limits:
- **Total chunks:** 500,000 (configurable via `SafetyConfig`)
- **Per-collection limits:** Configurable per collection
- **File size cap:** 1 MB (skip files larger than this)
- **Batch size:** 100 chunks per embedding API call

**Rationale:** claude-context's single hard limit is a blunt instrument. Our multi-level approach catches problems earlier (large files before they're parsed, collection limits before total is reached) and is configurable for different project sizes.

**Implementation:** `clew/models.py` (`SafetyConfig`), `clew/indexer/pipeline.py` — See [DESIGN.md Section 19](../DESIGN.md), [IMPLEMENTATION.md](../IMPLEMENTATION.md)

## Consequences

### Positive

- Avoided reinventing 8 patterns that claude-context has already validated
- Each adaptation improves on the original for our specific use case
- Clear provenance — future maintainers can reference claude-context for additional context
- The analysis process ([CLAUDE_CONTEXT_ANALYSIS.md](../CLAUDE_CONTEXT_ANALYSIS.md)) documented what we rejected and why, preventing re-evaluation

### Negative

- Risk of "not invented here" improvements that don't actually improve on the original
- Must maintain our own implementations rather than consuming upstream fixes

### Mitigated

- Each adaptation has explicit rationale — we can revisit if the rationale proves wrong
- claude-context remains a reference we can consult
