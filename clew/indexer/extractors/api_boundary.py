"""Cross-language API boundary matching.

Matches frontend fetch/axios API calls to Django URL patterns,
creating refined calls_api relationships that link frontend
entities to specific backend view entities.
"""

from __future__ import annotations

import re

from clew.indexer.relationships import Relationship

# Django path converter patterns: <int:pk>, <str:slug>, <uuid:id>, etc.
_DJANGO_CONVERTER_RE = re.compile(r"<\w+:\w+>")


def _normalize_url(url: str) -> str:
    """Strip trailing slash for comparison."""
    return url.rstrip("/")


class APIBoundaryMatcher:
    """Match frontend API calls to Django URL patterns."""

    def match(
        self,
        url_patterns: list[dict[str, str]],
        api_calls: list[Relationship],
    ) -> list[Relationship]:
        """Match API calls to URL patterns, returning refined relationships.

        Args:
            url_patterns: Django URL patterns from DjangoURLExtractor
            api_calls: Relationships with relationship="calls_api"

        Returns:
            Refined Relationship instances linking frontend to backend view.
        """
        if not url_patterns or not api_calls:
            return []

        compiled_patterns = self._compile_patterns(url_patterns)

        results: list[Relationship] = []
        for call in api_calls:
            call_url = _normalize_url(call.target_entity)
            matched = self._find_match(call_url, compiled_patterns)
            if matched:
                view = matched.get("view", "")
                target = f"{matched['file_path']}::{view}" if view else matched["file_path"]
                results.append(
                    Relationship(
                        source_entity=call.source_entity,
                        relationship="calls_api",
                        target_entity=target,
                        file_path=call.file_path,
                        confidence="inferred",
                    )
                )

        return results

    def _compile_patterns(
        self, url_patterns: list[dict[str, str]]
    ) -> list[tuple[re.Pattern[str], str, dict[str, str]]]:
        """Compile URL patterns into (regex, normalized_url, pattern_info) tuples."""
        compiled = []
        for pattern_info in url_patterns:
            raw_pattern = pattern_info.get("pattern", "")
            normalized = _normalize_url(raw_pattern)

            # Build regex: replace Django converters with wildcard segments
            regex_str = _DJANGO_CONVERTER_RE.sub("[^/]+", normalized)
            # Escape everything except our wildcards
            parts = re.split(r"(\[\^/\]\+)", regex_str)
            escaped_parts = []
            for part in parts:
                if part == "[^/]+":
                    escaped_parts.append(part)
                else:
                    escaped_parts.append(re.escape(part))
            regex = re.compile("^" + "".join(escaped_parts) + "$")

            compiled.append((regex, normalized, pattern_info))
        return compiled

    def _find_match(
        self,
        call_url: str,
        compiled_patterns: list[tuple[re.Pattern[str], str, dict[str, str]]],
    ) -> dict[str, str] | None:
        """Find the best matching URL pattern for a given API call URL."""
        # Try exact match first (after normalization)
        for _regex, normalized, info in compiled_patterns:
            if call_url == normalized:
                return info

        # Try regex match (handles parameterized URLs)
        for regex, _normalized, info in compiled_patterns:
            if regex.match(call_url):
                return info

        # Try prefix match (call URL starts with pattern prefix)
        for _regex, _normalized, info in compiled_patterns:
            static_prefix = _DJANGO_CONVERTER_RE.split(info.get("pattern", ""))[0]
            static_prefix = _normalize_url(static_prefix)
            if (
                static_prefix
                and call_url.startswith(static_prefix)
                and len(call_url) > len(static_prefix)
            ):
                return info

        return None
