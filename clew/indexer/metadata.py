"""Metadata extraction for indexed chunks.

Extracts app_name, layer, signature, and builds structured chunk IDs
from file paths and code entities.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

# Canonical test file detection patterns
_TEST_FILE_PATTERNS = [
    re.compile(r"(?:^|/)test_"),  # test_*.py
    re.compile(r"_test\.py$"),  # *_test.py
    re.compile(r"\.test\.\w+$"),  # *.test.ts/js
    re.compile(r"\.spec\.\w+$"),  # *.spec.ts/js
    re.compile(r"(?:^|/)tests/"),  # tests/ directory
    re.compile(r"(?:^|/)test/"),  # test/ directory
    re.compile(r"(?:^|/)__tests__/"),  # __tests__/ directory
    re.compile(r"(?:^|/)conftest\.py$"),  # pytest conftest
]


def is_test_file(file_path: str) -> bool:
    """Check if a file path matches test file patterns.

    Canonical implementation — import from here, not from extractors.
    """
    return any(p.search(file_path) for p in _TEST_FILE_PATTERNS)


# Layer classification mapping (filename -> layer)
LAYER_MAP: dict[str, str] = {
    "models.py": "model",
    "views.py": "view",
    "viewsets.py": "view",
    "serializers.py": "serializer",
    "tasks.py": "task",
    "service.py": "service",
    "services.py": "service",
    "admin.py": "admin",
    "forms.py": "form",
    "urls.py": "routing",
    "middleware.py": "middleware",
    "signals.py": "signal",
}

# Extensions that map to "component" layer
COMPONENT_EXTENSIONS = frozenset({".tsx", ".jsx"})


def classify_layer(file_path: str) -> str:
    """Classify file into an architectural layer.

    Returns one of: model, view, serializer, task, service, component, test,
    admin, form, routing, middleware, signal, other.
    """
    if is_test_file(file_path):
        return "test"

    path = PurePosixPath(file_path)
    filename = path.name

    if filename in LAYER_MAP:
        return LAYER_MAP[filename]

    if path.suffix in COMPONENT_EXTENSIONS:
        return "component"

    return "other"


def detect_app_name(file_path: str) -> str:
    """Detect app name from file path.

    For Django-style paths like 'backend/care/models.py', extracts 'care'.
    For other paths, uses the parent directory name.

    Tradeoff A resolution: Build this capability in Phase 2.
    """
    path = PurePosixPath(file_path)
    parts = path.parts

    if len(parts) < 2:
        return ""

    # Parent directory of the file
    return parts[-2]


def extract_signature(entity_type: str, content: str) -> str:
    """Extract function/method/class signature from code content.

    Returns the first line (up to the colon) for def/class definitions.
    Returns empty string for sections or empty content.
    """
    if entity_type in ("section", "toplevel") or not content:
        return ""

    first_line = content.strip().split("\n")[0].strip()
    if first_line.startswith(("def ", "class ", "async def ")):
        return first_line.rstrip(":")
    return ""


def build_chunk_id(
    file_path: str,
    entity_type: str,
    qualified_name: str,
    content: str = "",
) -> str:
    """Build structured chunk ID.

    Named entities: "file_path::entity_type::qualified_name"
    Anonymous/toplevel: "file_path::toplevel::sha256[:12]"
    """
    if qualified_name and entity_type not in ("section", "toplevel"):
        return f"{file_path}::{entity_type}::{qualified_name}"

    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"{file_path}::toplevel::{content_hash}"
