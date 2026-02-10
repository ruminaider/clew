"""Splitter fallback chain: tree-sitter -> token-recursive -> line split."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .tokenizer import count_tokens

if TYPE_CHECKING:
    from .parser import ASTParser
    from .strategies import PythonChunker  # noqa: F401

SPLIT_SEPARATORS = [
    "\n\nclass ",
    "\n\ndef ",
    "\n\n",
    "\n",
    " ",
]


@dataclass
class Chunk:
    """A chunk of source code or text."""

    content: str
    source: str  # "ast" or "fallback"
    file_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


def token_recursive_split(
    text: str,
    max_tokens: int,
    overlap_tokens: int = 200,
    separators: list[str] | None = None,
) -> list[str]:
    """Split text recursively by token count using semantic separators."""
    if count_tokens(text) <= max_tokens:
        return [text]

    separators = separators or SPLIT_SEPARATORS

    for separator in separators:
        parts = text.split(separator)
        if len(parts) == 1:
            continue

        chunks: list[str] = []
        current = parts[0]

        for part in parts[1:]:
            candidate = current + separator + part
            if count_tokens(candidate) <= max_tokens:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = _apply_overlap(chunks, part, overlap_tokens) if chunks else part

        if current.strip():
            chunks.append(current.strip())

        if all(count_tokens(c) <= max_tokens for c in chunks):
            return chunks

    return line_split(text, max_tokens, overlap_tokens)


def line_split(text: str, max_tokens: int, overlap_tokens: int = 200) -> list[str]:
    """Split text by lines, guaranteed to produce valid chunks."""
    lines = text.split("\n")
    chunks: list[str] = []
    current_lines: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)
        # If a single line exceeds max_tokens, split it by words
        if line_tokens > max_tokens:
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_tokens = 0
            chunks.extend(_word_split(line, max_tokens))
            continue
        if current_tokens + line_tokens > max_tokens and current_lines:
            chunks.append("\n".join(current_lines))
            overlap_lines = _get_overlap_lines(current_lines, overlap_tokens)
            current_lines = overlap_lines
            current_tokens = sum(count_tokens(ln) for ln in current_lines)
        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks


def _word_split(text: str, max_tokens: int) -> list[str]:
    """Split text by words when line-level splitting is insufficient."""
    words = text.split(" ")
    chunks: list[str] = []
    current_words: list[str] = []

    for word in words:
        candidate = current_words + [word]
        if count_tokens(" ".join(candidate)) > max_tokens and current_words:
            chunks.append(" ".join(current_words))
            current_words = [word]
        else:
            current_words = candidate

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def _apply_overlap(chunks: list[str], next_part: str, overlap_tokens: int) -> str:
    """Prepend overlap from the end of the last chunk."""
    if not chunks or overlap_tokens == 0:
        return next_part
    last_chunk = chunks[-1]
    lines = last_chunk.split("\n")
    overlap_lines = _get_overlap_lines(lines, overlap_tokens)
    overlap_text = "\n".join(overlap_lines)
    return overlap_text + "\n" + next_part if overlap_text else next_part


def _get_overlap_lines(lines: list[str], overlap_tokens: int) -> list[str]:
    """Get lines from the end that fit within overlap_tokens."""
    result: list[str] = []
    total = 0
    for line in reversed(lines):
        line_tokens = count_tokens(line)
        if total + line_tokens > overlap_tokens:
            break
        result.insert(0, line)
        total += line_tokens
    return result


def split_file(
    file_path: str,
    content: str,
    max_tokens: int,
    ast_parser: ASTParser,
    overlap_tokens: int = 200,
) -> list[Chunk]:
    """Split a file using the three-tier fallback chain.

    Tier 1: tree-sitter AST parsing (no overlap)
    Tier 2: Token-recursive splitting (with overlap)
    Tier 3: Line splitting (with overlap, guaranteed)
    """
    tree = ast_parser.parse_file(file_path, content)
    if tree:
        chunks = _extract_ast_chunks(tree, file_path, content, max_tokens)
        if chunks:
            return chunks

    text_chunks = token_recursive_split(content, max_tokens, overlap_tokens)
    return [Chunk(content=c, source="fallback", file_path=file_path) for c in text_chunks]


def _extract_ast_chunks(tree: Any, file_path: str, content: str, max_tokens: int) -> list[Chunk]:
    """Extract chunks from AST, returning empty list if no entities found."""
    from .strategies import PythonChunker

    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext != "py":
        return []

    chunker = PythonChunker()
    entities = list(chunker.extract_entities(tree, content))

    if not entities:
        return []

    chunks: list[Chunk] = []
    for entity in entities:
        meta = {
            "entity_type": entity.entity_type,
            "name": entity.name,
            "qualified_name": entity.qualified_name,
            "line_start": entity.line_start,
            "line_end": entity.line_end,
            "parent_class": entity.parent_class or "",
            "docstring": entity.docstring,
        }
        if count_tokens(entity.content) <= max_tokens:
            chunks.append(
                Chunk(content=entity.content, source="ast", file_path=file_path, metadata=meta)
            )
        else:
            sub_chunks = token_recursive_split(entity.content, max_tokens, overlap_tokens=200)
            chunks.extend(
                Chunk(content=c, source="fallback", file_path=file_path, metadata=meta)
                for c in sub_chunks
            )

    return chunks
