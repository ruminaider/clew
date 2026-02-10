# Three-Layer Codebase Knowledge Design

**Status:** Brainstorm — captures future direction, not V1 scope
**Date:** 2026-02-06
**Context:** Brainstorm following claude-context evaluation. Explores whether clew needs knowledge graphs and what it means to combine embeddings with structured relationships.

---

## Problem Statement

Vector search (clew V1) answers: "What code is semantically similar to my question?" But four classes of queries remain hard:

| Problem | Why embeddings alone struggle |
|---------|-------------------------------|
| **Multi-hop reasoning** ("What happens when a subscription cancellation has an active fill in transit?") | Finds individual pieces but can't chain subscription → order → fill → shipment |
| **Impact analysis** ("If I change the Prescription model, what else breaks?") | Finds things that mention Prescription, misses indirect dependents |
| **Data flow navigation** ("How does data flow from Shopify webhook to prescription creation?") | Finds entry/exit points but can't trace the thread through 6 files |
| **Business-to-code mapping** ("What code implements the prescription fulfillment process?") | "Patient receives care recommendation" returns nothing — no code chunk contains that phrase |

## Key Insight: Three Layers of Knowing a Codebase

| Layer | Question it answers | Best tool | Timing |
|-------|-------------------|-----------|--------|
| **Semantic** | "What code is *about* this topic?" | Vector search (clew V1) | Now |
| **Structural** | "What *calls/depends on/imports* what?" | Graph from AST + imports | V1.2 |
| **Business** | "What code *implements* this business process step?" | Explicit mapping (blueprint → code) | V2+ |

No single layer answers the hard questions. All three together do.

**Decision: We do NOT need Graphiti or a full knowledge graph.** Graphiti's temporal/contradiction features are designed for conversational AI (evolving user preferences), not codebases. Code entities are deterministic facts extracted from AST, not probabilistic inferences. Code doesn't have "contradictions" — it has versions (git handles that).

---

## Layer 1: Semantic (V1 — Designed, Ready to Build)

This is clew as currently designed in DESIGN.md and IMPLEMENTATION.md. Voyage AI embeddings, Qdrant hybrid search, BM25, reranking.

No changes needed. Proceed with implementation.

---

## Layer 2: Structural (V1.2 — Designed in Brainstorm)

A code relationship graph extracted deterministically from AST at index time. Stored in SQLite alongside existing caches.

### Schema

```sql
CREATE TABLE code_relationships (
    source_entity TEXT NOT NULL,   -- "care/models.py::Prescription"
    relationship  TEXT NOT NULL,   -- "imports", "calls", "inherits", etc.
    target_entity TEXT NOT NULL,   -- "care/service.py::create_order"
    file_path     TEXT NOT NULL,   -- source file where relationship was found
    confidence    TEXT DEFAULT 'static',  -- 'static' (AST) vs 'inferred'
    PRIMARY KEY (source_entity, relationship, target_entity)
);
```

### Relationship Types

| Language | Relationship | AST Node Types | Confidence |
|----------|-------------|----------------|------------|
| Python | `imports` | `import_statement`, `import_from_statement` | static |
| Python | `inherits` | `class_definition` → base classes | static |
| Python | `calls` | `call` expressions | inferred |
| Python | `decorates` | `decorator` | static |
| TypeScript | `imports` | `import_declaration` | static |
| TypeScript | `calls_api` | `fetch()`, `axios.*()`, API client patterns | inferred |
| TypeScript | `renders` | JSX component usage | static |
| Both | `tests` | Files in `tests/` importing the target | static |

### Cross-Language: API Boundary Tracking

Same-language relationships are explicit (imports). Cross-language relationships connect through API contracts — URL patterns both sides know about:

```
Frontend (TypeScript)              API Boundary              Backend (Python)
PrescriptionList.tsx  ──GET /api/care/prescriptions/──>  PrescriptionViewSet
PaymentForm.tsx       ──POST /api/ecomm/checkout/──────>  CheckoutView.post
```

Extraction:
- **Backend:** Parse `urls.py` with tree-sitter. Django URL confs map path → view.
- **Frontend:** Scan for API calls (fetch, axios, custom client). Regex-extractable for the common case.
- **Bridge:** Match frontend URL strings to backend URL patterns. Stored as `calls_api` with `confidence='inferred'`.

Dynamic URLs (template strings, computed paths) won't be caught. Accepted imperfection — static analysis gets 80% of the value.

### Extraction Integration

Relationships are extracted alongside chunking in the existing indexing pipeline:

```
File → tree-sitter parse → extract chunks (existing)
                         → extract relationships (new)
                         → store in code_relationships
```

No second pass. Same AST, same parse.

```python
# clew/indexer/relationships.py
class RelationshipExtractor:
    def __init__(self, ast_parser: ASTParser, db: CacheDB):
        self.parser = ast_parser
        self.db = db

    def extract_from_file(self, file_path: str, tree) -> list[Relationship]:
        language = self.parser.get_language(file_path)
        if language == "python":
            return self._extract_python(file_path, tree)
        elif language in ("typescript", "tsx"):
            return self._extract_typescript(file_path, tree)
        return []

    def store(self, relationships: list[Relationship]):
        """Batch insert into code_relationships table."""
        ...
```

### MCP Tool: `trace`

```typescript
// Input
{
  entity: string,                  // "care/models.py::Prescription"
  direction: "inbound" | "outbound" | "both",
  max_depth?: number,              // Default 2, max 5
  relationship_types?: string[],   // Filter: ["imports", "calls", "calls_api"]
}

// Output
{
  entity: string,
  relationships: Array<{
    source: string,
    relationship: string,
    target: string,
    confidence: "static" | "inferred",
    depth: number,
  }>,
  blueprint_context?: {            // If entity maps to a blueprint step (V2)
    blueprint: string,
    step: string,
    lane: string,
  }
}
```

### Call Graph Limitations

Static analysis can't resolve dynamic dispatch, `getattr`, computed method names, or dependency injection. We extract what's statically visible and mark confidence accordingly. The agent treats inferred edges as hints, not guarantees.

---

## Layer 3: Business (V2+ — Depends on Separate Blueprint Tool)

### Prerequisite: Blueprint Tool (Separate Project)

A standalone tool (like GoRules but for service processes) that:
- Has a visual editor for creating/editing service blueprints
- Produces YAML files in a custom graph schema (GoRules JDM-inspired)
- Is usable across organizations (not clew-specific)
- Outputs version-controlled YAML files that live in the project repo

This is a separate project. Code-search does not create blueprints — it consumes them.

### Blueprint YAML Format (Option B — GoRules-Inspired Graph Schema)

Service blueprints are non-linear — they have branches, parallel paths, decision points, and failure paths. The format uses an explicit node+edge graph (not a linear sequence):

```yaml
schema: service-blueprint/1.0
name: prescription-fulfillment
version: "1.0.0"

lanes:
  patient:
    label: Patient Actions
    visibility: external
  frontstage:
    label: Frontstage
    visibility: external
  backstage:
    label: Backstage
    visibility: internal
  support:
    label: External Partners
    visibility: internal

nodes:
  complete_consultation:
    type: action
    lane: frontstage
    label: Complete Consultation
    entry_points:
      - file: "backend/consults/wheel/tasks.py"
        symbol: "send_wheel_consult"
    next: evaluate_treatment

  evaluate_treatment:
    type: switch
    lane: backstage
    label: Treatment Decision
    cases:
      - when: "needs_prescription"
        next: create_prescription
      - when: "otc_only"
        next: recommend_otc
    default: create_prescription

  create_prescription:
    type: action
    lane: backstage
    label: Create Prescription
    entry_points:
      - file: "backend/care/service.py"
        symbol: "create_prescription"
    next: fulfill_order

  fulfill_order:
    type: parallel
    lane: backstage
    label: Fulfill Order
    branches:
      - submit_to_pharmacy
      - notify_patient
    join: delivery_tracking

  submit_to_pharmacy:
    type: action
    lane: support
    label: Submit to Pharmacy
    entry_points:
      - file: "backend/shipping/precision/client.py"
        symbol: "submit_order"
    error:
      retry: { limit: 3, backoff: exponential }
      catch: pharmacy_submission_failed

  pharmacy_submission_failed:
    type: action
    lane: frontstage
    label: Notify Pharmacy Error
    entry_points:
      - file: "backend/notifications/service.py"
        symbol: "send_pharmacy_error_notification"
    next: null  # terminal
```

**Why this format:**
- Conceptual consistency with GoRules (team already thinks in node+edge graphs)
- Lanes are first-class (not metadata), matching service blueprint structure
- Supports: branching (`switch`), parallel paths (`parallel` + `join`), error handling (`error` + `catch`)
- Not a workflow engine — it's a mapping format. We're not executing these, we're querying them.

### How Code-Search Consumes Blueprints (V2)

At index time, read YAML files and build a lookup table:

```sql
CREATE TABLE IF NOT EXISTS blueprint_steps (
    blueprint_name TEXT NOT NULL,
    step_id TEXT NOT NULL,
    step_label TEXT NOT NULL,
    step_type TEXT NOT NULL,        -- 'action', 'switch', 'parallel'
    lane TEXT,
    next_steps TEXT,                -- JSON array of step IDs
    entry_points TEXT,              -- JSON array of {file, symbol}
    PRIMARY KEY (blueprint_name, step_id)
);
```

**Reverse lookup:** Developer changes `care/service.py::create_prescription` → clew answers "this implements Step 3 of Prescription Fulfillment (backstage lane)."

**Config:**

```yaml
# In project config.yaml
blueprints:
  directory: "blueprints/"
  auto_index: true
```

### MCP Tool: `blueprint` (V2)

```typescript
// Input
{
  action: "list" | "get" | "find_step",
  blueprint_name?: string,     // For "get"
  code_entity?: string,        // For "find_step" — reverse lookup
}

// Output (get)
{
  name: string,
  steps: Array<{
    id: string,
    label: string,
    type: string,
    lane: string,
    entry_points: Array<{ file: string, symbol: string }>,
    next: string[],
  }>
}

// Output (find_step)
{
  matches: Array<{
    blueprint: string,
    step_id: string,
    step_label: string,
    lane: string,
  }>
}
```

---

## Agent Query Flow: All Three Layers

An agent debugging "subscription cancellation with active prescription fill in transit":

1. **`search`** (Layer 1 — Semantic) → find cancellation-related code by meaning
2. **`trace`** (Layer 2 — Structural) → follow outbound relationships from cancellation code to see what it touches (fills, shipments, notifications)
3. **`blueprint find_step`** (Layer 3 — Business) → discover this is Step 5 of "Subscription Lifecycle"
4. **`blueprint get`** (Layer 3 — Business) → see the full business flow to understand what *should* happen after cancellation

No single layer answers the question. The semantic layer finds the starting point, the structural layer traces the code path, and the business layer provides the "why" and "what should happen."

---

## Research Notes: Blueprint Format Alternatives Evaluated

The custom graph schema (Option B above) was chosen over three alternatives:

| Option | Format | Verdict |
|--------|--------|---------|
| **A: CNCF Serverless Workflow DSL 1.0** | YAML/JSON with `do`/`fork`/`switch`/`try` | Richest primitives but carries workflow-engine conceptual baggage (`call`, `with`). We're mapping, not executing. |
| **B: Custom GoRules-inspired graph** | YAML with explicit nodes + edges + lanes | **Selected.** Best fit: lanes are first-class, consistent with GoRules mental model, purpose-built for mapping. |
| **C: Dagu-style DAG** | YAML with `depends` arrays | Too simple — no formal branching or error-handling primitives. |

Key finding from research: there is no standard machine-readable format for service blueprints. BPMN 2.0 is the closest standard but is XML-based and process-centric (lacks "line of visibility" concept). Our custom schema fills a gap.

---

## Implementation Phasing

| Phase | What | Depends On |
|-------|------|------------|
| **V1** (build now) | Semantic layer: embeddings, hybrid search, reranking, 4 MCP tools | Nothing — ready to build |
| **V1.2** | Structural layer: `code_relationships` table, `RelationshipExtractor`, `trace` MCP tool | V1 complete |
| **V1.2+** | Cross-language API boundary tracking | V1.2 + frontend indexed |
| **V2** | Blueprint ingestion: `BlueprintReader`, `blueprint_steps` table, `blueprint` MCP tool | V1.2 + blueprint tool exists |

**V1 is complete and ready to build.** This document captures the roadmap beyond V1 so the design decisions aren't lost.

---

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| No Graphiti / no knowledge graph runtime | Graphiti's temporal features are for conversational AI, not codebases. Our relationships are deterministic AST facts, not LLM inferences. |
| SQLite for relationships (not Neo4j) | We already have SQLite for caching. Relationship queries are simple traversals (2-3 hops), not complex graph algorithms. Adding Neo4j for this is overkill. |
| Blueprint tool is a separate project | Different concern (process modeling vs code search), different users (business + devs vs developers), needs a visual editor. Code-search consumes the YAML output. |
| GoRules-inspired graph schema for blueprints | Team already thinks in node+edge graphs (GoRules JDM). Lanes are first-class. Not a workflow engine — a mapping format. |
| Static analysis with accepted imperfection | Dynamic dispatch, computed paths, and DI won't be captured. 80% coverage from static analysis is sufficient. Agent treats inferred edges as hints. |
