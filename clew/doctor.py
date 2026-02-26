"""Health check logic for `clew doctor` command."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import voyageai
from qdrant_client import QdrantClient

from clew.indexer.cache import CacheDB
from clew.indexer.git_tracker import GitChangeTracker


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    passed: bool
    detail: str
    fix_hint: str = ""


@dataclass
class DoctorReport:
    """Aggregated results from all health checks."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


def check_qdrant(qdrant_url: str, qdrant_api_key: str | None) -> CheckResult:
    """Check Qdrant connectivity and version."""
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=5)
        client.get_collections()
        # Extract host:port for display
        display_url = qdrant_url.replace("http://", "").replace("https://", "")
        return CheckResult(
            name="Qdrant",
            passed=True,
            detail=f"connected ({display_url})",
        )
    except Exception as e:
        return CheckResult(
            name="Qdrant",
            passed=False,
            detail=f"unreachable ({qdrant_url})",
            fix_hint=(
                "Start Qdrant: docker run -d --name clew-qdrant "
                "-p 6333:6333 -v clew_qdrant_data:/qdrant/storage "
                "qdrant/qdrant:v1.16.1\n"
                f"  Original error: {e}"
            ),
        )


def check_voyage(api_key: str) -> CheckResult:
    """Check Voyage API key validity with a minimal embed call."""
    if not api_key:
        return CheckResult(
            name="Voyage API",
            passed=False,
            detail="no API key set",
            fix_hint=(
                "Set VOYAGE_API_KEY environment variable. "
                "Get a free key at https://dash.voyageai.com/"
            ),
        )
    try:
        client = voyageai.Client(api_key=api_key)  # type: ignore[attr-defined]
        client.embed(["test"], model="voyage-code-3", input_type="document")
        return CheckResult(
            name="Voyage API",
            passed=True,
            detail="authenticated (voyage-code-3)",
        )
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "403" in error_str or "auth" in error_str:
            return CheckResult(
                name="Voyage API",
                passed=False,
                detail="authentication failed",
                fix_hint=(
                    "VOYAGE_API_KEY is invalid or expired. "
                    "Get a new key at https://dash.voyageai.com/"
                ),
            )
        return CheckResult(
            name="Voyage API",
            passed=False,
            detail=f"error: {e}",
            fix_hint="Check your network connection and Voyage API status.",
        )


def check_ollama(ollama_url: str) -> CheckResult:
    """Check Ollama connectivity."""
    try:
        import httpx

        response = httpx.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            model_str = ", ".join(models[:3]) if models else "no models"
            return CheckResult(
                name="Ollama",
                passed=True,
                detail=f"connected ({model_str})",
            )
        return CheckResult(
            name="Ollama",
            passed=False,
            detail=f"unexpected status {response.status_code}",
            fix_hint="Ensure Ollama is running: ollama serve",
        )
    except Exception:
        return CheckResult(
            name="Ollama",
            passed=False,
            detail=f"unreachable ({ollama_url})",
            fix_hint="Start Ollama: ollama serve",
        )


def check_cache_dir(cache_dir: Path) -> CheckResult:
    """Check that the cache directory exists and is writable."""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Test writability
        test_file = cache_dir / ".doctor_test"
        test_file.write_text("ok")
        test_file.unlink()
        return CheckResult(
            name="Cache dir",
            passed=True,
            detail=f"writable ({cache_dir})",
        )
    except OSError as e:
        return CheckResult(
            name="Cache dir",
            passed=False,
            detail=f"not writable ({cache_dir})",
            fix_hint=f"Fix permissions: chmod -R u+w {cache_dir}\n  Error: {e}",
        )


def check_index(
    cache_dir: Path, project_root: Path | None, collection_name: str = "code"
) -> CheckResult:
    """Check if index exists and how far behind HEAD it is."""
    try:
        cache = CacheDB(cache_dir)
    except Exception as e:
        return CheckResult(
            name="Index",
            passed=False,
            detail=f"cache error: {e}",
            fix_hint="Run: clew index . --full",
        )

    last_commit = cache.get_last_indexed_commit(collection_name)
    if not last_commit:
        return CheckResult(
            name="Index",
            passed=False,
            detail="not indexed",
            fix_hint="Run: clew index . --full",
        )

    root = project_root or Path.cwd()
    tracker = GitChangeTracker(root)
    staleness = tracker.check_staleness(last_commit)

    if staleness.commits_behind == 0 and not staleness.has_uncommitted_changes:
        # Try to get chunk count from Qdrant (best effort)
        chunk_count = _get_chunk_count(collection_name)
        count_str = f", {chunk_count:,} chunks" if chunk_count is not None else ""
        return CheckResult(
            name="Index",
            passed=True,
            detail=f"current (0 commits behind{count_str})",
        )

    detail_parts = []
    if staleness.commits_behind > 0:
        detail_parts.append(f"{staleness.commits_behind} commits behind")
    elif staleness.commits_behind == -1:
        detail_parts.append("unknown distance")
    if staleness.has_uncommitted_changes:
        detail_parts.append("uncommitted changes")

    return CheckResult(
        name="Index",
        passed=False,
        detail=f"stale ({', '.join(detail_parts)})",
        fix_hint="Run: clew index .",
    )


def _get_chunk_count(collection_name: str = "code") -> int | None:
    """Best-effort chunk count from Qdrant. Returns None on any error."""
    try:
        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=5)
        return client.count(collection_name=collection_name).count
    except Exception:
        return None


def check_enrichment(
    enrichment_provider: str,
    enrichment_model: str,
    env_anthropic_key: str,
    env_enrichment_key: str,
    ollama_url: str,
) -> CheckResult:
    """Check enrichment provider configuration and connectivity."""
    if enrichment_provider == "none":
        return CheckResult(
            name="Enrichment",
            passed=True,
            detail="not configured",
            fix_hint=(
                "Enrichment improves search quality. Configure in .clew.yaml:\n"
                "  enrichment_provider: anthropic  # Anthropic API (set ANTHROPIC_API_KEY)\n"
                "  enrichment_provider: openai     # any OpenAI-compatible API "
                "(set ENRICHMENT_API_KEY)\n"
                "  enrichment_provider: ollama     # local LLM via Ollama\n"
                "Or use /clew:enrich skill in Claude Code (uses your subscription)."
            ),
        )

    model_display = enrichment_model or "(default)"

    if enrichment_provider == "anthropic":
        if not env_anthropic_key:
            return CheckResult(
                name="Enrichment",
                passed=False,
                detail="provider 'anthropic' but ANTHROPIC_API_KEY not set",
                fix_hint="Set ANTHROPIC_API_KEY environment variable.",
            )
        return CheckResult(
            name="Enrichment",
            passed=True,
            detail=f"anthropic ({model_display})",
        )

    if enrichment_provider == "openai":
        if not env_enrichment_key:
            return CheckResult(
                name="Enrichment",
                passed=False,
                detail="provider 'openai' but ENRICHMENT_API_KEY not set",
                fix_hint="Set ENRICHMENT_API_KEY environment variable.",
            )
        return CheckResult(
            name="Enrichment",
            passed=True,
            detail=f"openai ({model_display})",
        )

    if enrichment_provider == "ollama":
        # Reuse Ollama connectivity check
        ollama_result = check_ollama(ollama_url)
        if not ollama_result.passed:
            return CheckResult(
                name="Enrichment",
                passed=False,
                detail="provider 'ollama' but Ollama unreachable",
                fix_hint=ollama_result.fix_hint,
            )
        return CheckResult(
            name="Enrichment",
            passed=True,
            detail=f"ollama ({model_display})",
        )

    return CheckResult(
        name="Enrichment",
        passed=False,
        detail=f"unknown provider '{enrichment_provider}'",
        fix_hint="Valid providers: anthropic, openai, ollama, none",
    )


def check_mcp_server() -> CheckResult:
    """Check that MCP server module can be imported (no missing deps)."""
    try:
        import clew.mcp_server  # noqa: F401

        return CheckResult(
            name="MCP server",
            passed=True,
            detail="ready",
        )
    except ImportError as e:
        return CheckResult(
            name="MCP server",
            passed=False,
            detail=f"import error: {e}",
            fix_hint="Reinstall: pip3 install clewdex",
        )


def run_doctor(
    project_root: Path | None = None,
    embedding_provider: str = "voyage",
    collection_name: str = "code",
    enrichment_provider: str = "none",
    enrichment_model: str = "",
) -> DoctorReport:
    """Run all health checks and return the aggregated report."""
    from clew.config import Environment

    env = Environment(project_root=project_root)

    report = DoctorReport()
    report.checks.append(
        check_qdrant(
            qdrant_url=env.QDRANT_URL,
            qdrant_api_key=env.QDRANT_API_KEY,
        )
    )

    # Provider-specific checks
    if embedding_provider == "ollama":
        report.checks.append(check_ollama(env.OLLAMA_URL))
    else:
        report.checks.append(check_voyage(env.VOYAGE_API_KEY))

    report.checks.append(check_cache_dir(env.CACHE_DIR))
    report.checks.append(check_index(env.CACHE_DIR, project_root, collection_name))
    report.checks.append(
        check_enrichment(
            enrichment_provider=enrichment_provider,
            enrichment_model=enrichment_model,
            env_anthropic_key=env.ANTHROPIC_API_KEY,
            env_enrichment_key=env.ENRICHMENT_API_KEY,
            ollama_url=env.OLLAMA_URL,
        )
    )
    report.checks.append(check_mcp_server())

    return report
