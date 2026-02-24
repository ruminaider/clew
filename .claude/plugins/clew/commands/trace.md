# /clew:trace

Relationship traversal. Traces code dependencies, callers, inheritance chains, and other structural relationships.

## When to Use

- Understanding what depends on a class or function (impact analysis)
- Tracing the call chain from an entry point to a database query
- Finding all subclasses of a base class
- Mapping imports and module dependencies
- Understanding how a test file relates to the code it tests
- Exploring API boundaries (frontend calling backend endpoints)

## When NOT to Use

- Finding code by concept or behavior (use /clew:search)
- Reading source code (use Read)
- Finding literal text patterns (use grep)

## Usage

Call the `trace` MCP tool:

```
trace(entity="app/models.py::Prescription")
trace(entity="app/views.py::CheckoutView.process_payment", direction="outbound")
trace(entity="PrescriptionSerializer", direction="inbound", max_depth=3)
trace(entity="app/auth.py::JWTMiddleware", relationship_types=["calls", "imports"])
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `entity` | required | Entity identifier to trace |
| `direction` | "both" | "inbound" (who uses this?), "outbound" (what does this use?), "both" |
| `max_depth` | 2 | How many hops to follow (1-5) |
| `relationship_types` | all | Filter: "imports", "calls", "inherits", "decorates", "renders", "tests", "calls_api" |
| `language` | none | Prefer entities in this language ("python", "typescript") |

### Entity Format

Entities use the format `file_path::QualifiedName`:

- `app/models.py::Prescription` -- a class
- `app/models.py::Prescription.get_refills` -- a method
- `app/views.py::process_checkout` -- a top-level function
- `Prescription` -- short form (clew resolves to the full entity)

Short-form names (without the file path prefix) work when unambiguous. Clew will resolve them and show the resolved entity in the response.

## Reading Results

Results contain a list of relationships, each with:

- `source_entity` -- the entity on the "from" side
- `relationship` -- the type (imports, calls, inherits, etc.)
- `target_entity` -- the entity on the "to" side
- `depth` -- how many hops from the queried entity
- `confidence` -- extraction confidence score

Follow up with Read to inspect the source of any entity that appears in the trace.
