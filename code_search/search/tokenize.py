"""Code-aware tokenization for BM25 sparse vectors.

Sparse vector values are raw term counts (not normalized).
Qdrant applies IDF weighting at query time via Modifier.IDF.
See Tradeoff E resolution.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CAMEL_CASE_PATTERN = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)")
IDENTIFIER_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


@dataclass
class SparseVector:
    """Sparse vector for BM25 search."""

    indices: list[int]
    values: list[float]


def split_identifier(identifier: str) -> list[str]:
    """Split a code identifier into sub-tokens.

    Handles camelCase, PascalCase, snake_case, and ALLCAPS.

    Examples:
        "getUserById" -> ["get", "user", "by", "id"]
        "get_user_by_id" -> ["get", "user", "by", "id"]
        "HTMLParser" -> ["html", "parser"]
    """
    parts: list[str] = []
    for segment in identifier.split("_"):
        if not segment:
            continue
        camel_parts = CAMEL_CASE_PATTERN.findall(segment)
        if camel_parts:
            parts.extend(p.lower() for p in camel_parts)
        else:
            parts.append(segment.lower())
    return parts if parts else [identifier.lower()]


def tokenize_code(text: str) -> list[str]:
    """Tokenize code text into searchable tokens.

    Extracts identifiers, splits camelCase/snake_case,
    and returns deduplicated lowercase tokens (length > 1).
    """
    tokens: list[str] = []
    identifiers = IDENTIFIER_PATTERN.findall(text)
    for ident in identifiers:
        tokens.append(ident.lower())
        parts = split_identifier(ident)
        tokens.extend(parts)

    seen: set[str] = set()
    unique: list[str] = []
    for t in tokens:
        if t not in seen and len(t) > 1:
            seen.add(t)
            unique.append(t)
    return unique


def _extract_all_tokens(text: str) -> list[str]:
    """Extract ALL tokens from text (with duplicates) for term counting."""
    tokens: list[str] = []
    identifiers = IDENTIFIER_PATTERN.findall(text)
    for ident in identifiers:
        tokens.append(ident.lower())
        parts = split_identifier(ident)
        tokens.extend(parts)
    return [t for t in tokens if len(t) > 1]


def _token_to_index(token: str) -> int:
    """Map token to sparse vector index using deterministic hash."""
    h = hashlib.md5(token.encode()).hexdigest()  # noqa: S324
    return int(h, 16) % (2**31 - 1)


def text_to_sparse_vector(text: str) -> SparseVector:
    """Convert text to a BM25-style sparse vector.

    Uses raw term counts as values (not normalized).
    Qdrant applies IDF weighting at query time via Modifier.IDF.
    """
    all_tokens = _extract_all_tokens(text)
    if not all_tokens:
        return SparseVector(indices=[], values=[])

    # Count raw term frequencies
    freq: dict[str, int] = {}
    for t in all_tokens:
        freq[t] = freq.get(t, 0) + 1

    indices: list[int] = []
    values: list[float] = []
    for token, count in sorted(freq.items()):
        indices.append(_token_to_index(token))
        values.append(float(count))  # Raw count, not normalized

    return SparseVector(indices=indices, values=values)
