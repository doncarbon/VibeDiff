"""Tests for baseline save/load/apply and CLI command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from vibediff.cli import (
    BASELINE_FILE,
    CACHE_DIR,
    _apply_baseline,
    _load_baseline,
    _save_baseline,
    main,
)
from vibediff.analyze import Finding


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Point CACHE_DIR to a temp directory."""
    cache = tmp_path / ".vibediff-cache"
    monkeypatch.setattr("vibediff.cli.CACHE_DIR", str(cache))
    return cache


class TestBaselineHelpers:
    def test_save_and_load(self, cache_dir):
        signals = {"comment_density", "verbose_names"}
        _save_baseline(signals)
        loaded = _load_baseline()
        assert loaded == signals

    def test_load_returns_none_when_missing(self, cache_dir):
        assert _load_baseline() is None

    def test_load_returns_none_on_bad_json(self, cache_dir):
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / BASELINE_FILE).write_text("not json{")
        assert _load_baseline() is None

    def test_apply_baseline_filters(self):
        findings = [
            Finding(signal="comment_density", detail="d", severity=0.5),
            Finding(signal="verbose_names", detail="d", severity=0.3),
            Finding(signal="low_burstiness", detail="d", severity=0.7),
        ]
        baseline = {"comment_density", "verbose_names"}
        result = _apply_baseline(findings, baseline)
        assert len(result) == 1
        assert result[0].signal == "low_burstiness"

    def test_apply_baseline_none_passes_through(self):
        findings = [Finding(signal="a", detail="d", severity=0.5)]
        result = _apply_baseline(findings, None)
        assert result == findings


class TestBaselineCLI:
    @pytest.fixture
    def tmp_repo(self, tmp_path, monkeypatch):
        import subprocess
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("vibediff.cli.CACHE_DIR", str(tmp_path / ".vibediff-cache"))
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)

        (tmp_path / "app.py").write_text("def foo():\n    pass\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

        (tmp_path / "app.py").write_text(
            "# Initialize the logger\n"
            "import logging\n"
            "logger = logging.getLogger(__name__)\n\n"
            "# Handle the request\n"
            "def handle_incoming_user_request(request):\n"
            '    """Handle an incoming user request."""\n'
            "    if request is None:\n"
            "        return None\n"
            "    # Return the data\n"
            "    return request.data\n"
        )
        return tmp_path

    def test_baseline_saves_signals(self, tmp_repo):
        runner = CliRunner()
        result = runner.invoke(main, ["baseline", "HEAD"])
        assert result.exit_code == 0
        assert "Baseline saved" in result.output

        baseline_path = tmp_repo / ".vibediff-cache" / "baseline.json"
        assert baseline_path.exists()
        data = json.loads(baseline_path.read_text())
        assert len(data["signals"]) > 0

    def test_baseline_clear(self, tmp_repo):
        runner = CliRunner()
        # First save
        runner.invoke(main, ["baseline", "HEAD"])
        # Then clear
        result = runner.invoke(main, ["baseline", "--clear"])
        assert result.exit_code == 0
        assert "Baseline cleared" in result.output
        assert not (tmp_repo / ".vibediff-cache" / "baseline.json").exists()

    def test_baseline_clear_when_none(self, tmp_repo):
        runner = CliRunner()
        result = runner.invoke(main, ["baseline", "--clear"])
        assert result.exit_code == 0
        assert "No baseline" in result.output

    def test_review_respects_baseline(self, tmp_repo):
        runner = CliRunner()
        # Review without baseline
        r1 = runner.invoke(main, ["review", "HEAD", "--format", "json", "--no-fingerprint"])
        assert r1.exit_code == 0
        data1 = json.loads(r1.output)
        findings1 = data1["ai_detection"]["findings"]

        # Set baseline
        runner.invoke(main, ["baseline", "HEAD"])

        # Review with baseline — should suppress baselined signals
        r2 = runner.invoke(main, ["review", "HEAD", "--format", "json", "--no-fingerprint"])
        assert r2.exit_code == 0
        data2 = json.loads(r2.output)
        findings2 = data2["ai_detection"]["findings"]
        assert len(findings2) <= len(findings1)

    def test_review_no_baseline_flag(self, tmp_repo):
        runner = CliRunner()
        # Set baseline
        runner.invoke(main, ["baseline", "HEAD"])

        # Review with --no-baseline should show everything
        r = runner.invoke(main, ["review", "HEAD", "--format", "json", "--no-fingerprint", "--no-baseline"])
        assert r.exit_code == 0
        data = json.loads(r.output)
        # Should have findings despite baseline
        assert "ai_detection" in data
