"""Tests for the doctor command and health check logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from clew.cli import app
from clew.doctor import (
    CheckResult,
    DoctorReport,
    check_cache_dir,
    check_enrichment,
    check_index,
    check_mcp_server,
    check_qdrant,
    check_voyage,
    run_doctor,
)

runner = CliRunner()


class TestCheckQdrant:
    @patch("clew.doctor.QdrantClient")
    def test_qdrant_healthy(self, mock_client_cls: Mock) -> None:
        mock_client_cls.return_value.get_collections.return_value = Mock(collections=[])
        result = check_qdrant("http://localhost:6333", None)
        assert result.passed is True
        assert "connected" in result.detail
        assert "localhost:6333" in result.detail

    @patch("clew.doctor.QdrantClient")
    def test_qdrant_unreachable(self, mock_client_cls: Mock) -> None:
        mock_client_cls.side_effect = ConnectionError("refused")
        result = check_qdrant("http://localhost:6333", None)
        assert result.passed is False
        assert "unreachable" in result.detail
        assert result.fix_hint  # has a fix hint

    @patch("clew.doctor.QdrantClient")
    def test_qdrant_strips_protocol(self, mock_client_cls: Mock) -> None:
        mock_client_cls.return_value.get_collections.return_value = Mock(collections=[])
        result = check_qdrant("https://my-qdrant:6333", None)
        assert result.passed is True
        assert "my-qdrant:6333" in result.detail
        assert "https://" not in result.detail


class TestCheckVoyage:
    def test_voyage_no_key(self) -> None:
        result = check_voyage("")
        assert result.passed is False
        assert "no API key" in result.detail
        assert "VOYAGE_API_KEY" in result.fix_hint

    @patch("clew.doctor.voyageai")
    def test_voyage_valid_key(self, mock_voyage: Mock) -> None:
        result = check_voyage("voy-test-key")
        assert result.passed is True
        assert "authenticated" in result.detail
        assert "voyage-code-3" in result.detail

    @patch("clew.doctor.voyageai")
    def test_voyage_auth_error(self, mock_voyage: Mock) -> None:
        mock_voyage.Client.return_value.embed.side_effect = Exception("401 Unauthorized")
        result = check_voyage("voy-bad-key")
        assert result.passed is False
        assert "authentication failed" in result.detail
        assert "dash.voyageai.com" in result.fix_hint

    @patch("clew.doctor.voyageai")
    def test_voyage_network_error(self, mock_voyage: Mock) -> None:
        mock_voyage.Client.return_value.embed.side_effect = ConnectionError("timeout")
        result = check_voyage("voy-test-key")
        assert result.passed is False
        assert "error" in result.detail


class TestCheckCacheDir:
    def test_cache_dir_writable(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / ".clew"
        result = check_cache_dir(cache_dir)
        assert result.passed is True
        assert "writable" in result.detail
        assert str(cache_dir) in result.detail

    def test_cache_dir_creates_if_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "deep" / "nested" / ".clew"
        assert not cache_dir.exists()
        result = check_cache_dir(cache_dir)
        assert result.passed is True
        assert cache_dir.exists()

    def test_cache_dir_not_writable(self) -> None:
        # Use a path that can't be created
        cache_dir = Path("/proc/nonexistent/.clew")
        result = check_cache_dir(cache_dir)
        assert result.passed is False
        assert "not writable" in result.detail


class TestCheckIndex:
    @patch("clew.doctor._get_chunk_count", return_value=1247)
    @patch("clew.doctor.GitChangeTracker")
    @patch("clew.doctor.CacheDB")
    def test_index_current(
        self, mock_cache_cls: Mock, mock_tracker_cls: Mock, mock_count: Mock, tmp_path: Path
    ) -> None:
        mock_cache_cls.return_value.get_last_indexed_commit.return_value = "abc123"
        mock_tracker_cls.return_value.check_staleness.return_value = Mock(
            is_stale=False, commits_behind=0, has_uncommitted_changes=False
        )
        result = check_index(tmp_path, tmp_path)
        assert result.passed is True
        assert "current" in result.detail
        assert "1,247 chunks" in result.detail

    @patch("clew.doctor.CacheDB")
    def test_index_not_indexed(self, mock_cache_cls: Mock, tmp_path: Path) -> None:
        mock_cache_cls.return_value.get_last_indexed_commit.return_value = None
        result = check_index(tmp_path, tmp_path)
        assert result.passed is False
        assert "not indexed" in result.detail
        assert "clew index" in result.fix_hint

    @patch("clew.doctor.GitChangeTracker")
    @patch("clew.doctor.CacheDB")
    def test_index_stale_commits_behind(
        self, mock_cache_cls: Mock, mock_tracker_cls: Mock, tmp_path: Path
    ) -> None:
        mock_cache_cls.return_value.get_last_indexed_commit.return_value = "abc123"
        mock_tracker_cls.return_value.check_staleness.return_value = Mock(
            is_stale=True, commits_behind=5, has_uncommitted_changes=False
        )
        result = check_index(tmp_path, tmp_path)
        assert result.passed is False
        assert "5 commits behind" in result.detail

    @patch("clew.doctor.GitChangeTracker")
    @patch("clew.doctor.CacheDB")
    def test_index_stale_uncommitted(
        self, mock_cache_cls: Mock, mock_tracker_cls: Mock, tmp_path: Path
    ) -> None:
        mock_cache_cls.return_value.get_last_indexed_commit.return_value = "abc123"
        mock_tracker_cls.return_value.check_staleness.return_value = Mock(
            is_stale=True, commits_behind=0, has_uncommitted_changes=True
        )
        result = check_index(tmp_path, tmp_path)
        assert result.passed is False
        assert "uncommitted changes" in result.detail

    @patch("clew.doctor.CacheDB")
    def test_index_cache_error(self, mock_cache_cls: Mock, tmp_path: Path) -> None:
        mock_cache_cls.side_effect = RuntimeError("corrupt db")
        result = check_index(tmp_path, tmp_path)
        assert result.passed is False
        assert "cache error" in result.detail


class TestCheckEnrichment:
    def test_none_provider_passes_with_hint(self) -> None:
        result = check_enrichment("none", "", "", "", "")
        assert result.passed is True
        assert "not configured" in result.detail
        assert result.fix_hint  # has suggestion

    def test_anthropic_with_key_passes(self) -> None:
        result = check_enrichment("anthropic", "claude-haiku-4-5-20251001", "test-key", "", "")
        assert result.passed is True
        assert "anthropic" in result.detail

    def test_anthropic_no_key_fails(self) -> None:
        result = check_enrichment("anthropic", "", "", "", "")
        assert result.passed is False
        assert "ANTHROPIC_API_KEY" in result.fix_hint

    def test_openai_with_key_passes(self) -> None:
        result = check_enrichment("openai", "gpt-4o-mini", "", "test-key", "")
        assert result.passed is True
        assert "openai" in result.detail

    def test_openai_no_key_fails(self) -> None:
        result = check_enrichment("openai", "", "", "", "")
        assert result.passed is False
        assert "ENRICHMENT_API_KEY" in result.fix_hint

    @patch("clew.doctor.check_ollama")
    def test_ollama_passes_when_reachable(self, mock_check: Mock) -> None:
        mock_check.return_value = CheckResult(name="Ollama", passed=True, detail="connected")
        result = check_enrichment("ollama", "qwen3:8b", "", "", "http://localhost:11434")
        assert result.passed is True
        assert "ollama" in result.detail

    @patch("clew.doctor.check_ollama")
    def test_ollama_fails_when_unreachable(self, mock_check: Mock) -> None:
        mock_check.return_value = CheckResult(
            name="Ollama", passed=False, detail="unreachable", fix_hint="ollama serve"
        )
        result = check_enrichment("ollama", "qwen3:8b", "", "", "http://localhost:11434")
        assert result.passed is False
        assert "unreachable" in result.detail

    def test_unknown_provider_fails(self) -> None:
        result = check_enrichment("unknown", "", "", "", "")
        assert result.passed is False
        assert "unknown" in result.detail


class TestCheckMcpServer:
    def test_mcp_server_importable(self) -> None:
        result = check_mcp_server()
        assert result.passed is True
        assert result.detail == "ready"

    def test_mcp_server_import_error(self) -> None:
        # Force import error by removing the module from sys.modules
        import sys

        saved = sys.modules.pop("clew.mcp_server", None)
        sys.modules["clew.mcp_server"] = None  # type: ignore[assignment]
        try:
            result = check_mcp_server()
            assert result.passed is False
            assert "import error" in result.detail
        finally:
            if saved is not None:
                sys.modules["clew.mcp_server"] = saved
            else:
                sys.modules.pop("clew.mcp_server", None)


class TestDoctorReport:
    def test_all_passed(self) -> None:
        report = DoctorReport(
            checks=[
                CheckResult(name="A", passed=True, detail="ok"),
                CheckResult(name="B", passed=True, detail="ok"),
            ]
        )
        assert report.all_passed is True

    def test_some_failed(self) -> None:
        report = DoctorReport(
            checks=[
                CheckResult(name="A", passed=True, detail="ok"),
                CheckResult(name="B", passed=False, detail="bad"),
            ]
        )
        assert report.all_passed is False

    def test_empty_report(self) -> None:
        report = DoctorReport()
        assert report.all_passed is True


class TestRunDoctor:
    @patch("clew.doctor.check_mcp_server")
    @patch("clew.doctor.check_enrichment")
    @patch("clew.doctor.check_index")
    @patch("clew.doctor.check_cache_dir")
    @patch("clew.doctor.check_voyage")
    @patch("clew.doctor.check_qdrant")
    def test_run_doctor_all_pass(
        self,
        mock_qdrant: Mock,
        mock_voyage: Mock,
        mock_cache: Mock,
        mock_index: Mock,
        mock_enrichment: Mock,
        mock_mcp: Mock,
    ) -> None:
        mock_qdrant.return_value = CheckResult(name="Qdrant", passed=True, detail="ok")
        mock_voyage.return_value = CheckResult(name="Voyage API", passed=True, detail="ok")
        mock_cache.return_value = CheckResult(name="Cache dir", passed=True, detail="ok")
        mock_index.return_value = CheckResult(name="Index", passed=True, detail="ok")
        mock_enrichment.return_value = CheckResult(name="Enrichment", passed=True, detail="ok")
        mock_mcp.return_value = CheckResult(name="MCP server", passed=True, detail="ok")

        report = run_doctor()
        assert report.all_passed is True
        assert len(report.checks) == 6

    @patch("clew.doctor.check_mcp_server")
    @patch("clew.doctor.check_enrichment")
    @patch("clew.doctor.check_index")
    @patch("clew.doctor.check_cache_dir")
    @patch("clew.doctor.check_voyage")
    @patch("clew.doctor.check_qdrant")
    def test_run_doctor_partial_failure(
        self,
        mock_qdrant: Mock,
        mock_voyage: Mock,
        mock_cache: Mock,
        mock_index: Mock,
        mock_enrichment: Mock,
        mock_mcp: Mock,
    ) -> None:
        mock_qdrant.return_value = CheckResult(
            name="Qdrant", passed=False, detail="unreachable", fix_hint="Start Qdrant"
        )
        mock_voyage.return_value = CheckResult(name="Voyage API", passed=True, detail="ok")
        mock_cache.return_value = CheckResult(name="Cache dir", passed=True, detail="ok")
        mock_index.return_value = CheckResult(name="Index", passed=True, detail="ok")
        mock_enrichment.return_value = CheckResult(name="Enrichment", passed=True, detail="ok")
        mock_mcp.return_value = CheckResult(name="MCP server", passed=True, detail="ok")

        report = run_doctor()
        assert report.all_passed is False


class TestDoctorCLI:
    @patch("clew.doctor.run_doctor")
    def test_doctor_all_pass_exit_0(self, mock_run: Mock) -> None:
        mock_run.return_value = DoctorReport(
            checks=[
                CheckResult(name="Qdrant", passed=True, detail="connected"),
                CheckResult(name="Voyage API", passed=True, detail="ok"),
                CheckResult(name="Cache dir", passed=True, detail="writable"),
                CheckResult(name="Index", passed=True, detail="current"),
                CheckResult(name="MCP server", passed=True, detail="ready"),
            ]
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0

    @patch("clew.doctor.run_doctor")
    def test_doctor_failure_exit_1(self, mock_run: Mock) -> None:
        mock_run.return_value = DoctorReport(
            checks=[
                CheckResult(
                    name="Qdrant",
                    passed=False,
                    detail="unreachable",
                    fix_hint="Start Qdrant with docker",
                ),
                CheckResult(name="Voyage API", passed=True, detail="ok"),
            ]
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1

    @patch("clew.doctor.run_doctor")
    def test_doctor_shows_fix_hints(self, mock_run: Mock) -> None:
        mock_run.return_value = DoctorReport(
            checks=[
                CheckResult(
                    name="Voyage API",
                    passed=False,
                    detail="no API key",
                    fix_hint="Set VOYAGE_API_KEY",
                ),
            ]
        )
        result = runner.invoke(app, ["doctor"])
        assert "Set VOYAGE_API_KEY" in result.output

    def test_doctor_in_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "doctor" in result.output

    def test_doctor_help(self) -> None:
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower()
