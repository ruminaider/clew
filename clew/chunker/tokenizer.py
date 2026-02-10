"""Voyage tokenizer wrapper for accurate token counting."""

from functools import lru_cache

from transformers import AutoTokenizer, PreTrainedTokenizerBase


@lru_cache(maxsize=1)
def get_tokenizer() -> PreTrainedTokenizerBase:
    """Load and cache the Voyage tokenizer."""
    return AutoTokenizer.from_pretrained("voyageai/voyage-code-3")


def count_tokens(text: str) -> int:
    """Count tokens using Voyage tokenizer."""
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))


def chunk_fits(chunk: str, max_tokens: int = 4000) -> bool:
    """Check if chunk is within token limit."""
    return count_tokens(chunk) <= max_tokens
