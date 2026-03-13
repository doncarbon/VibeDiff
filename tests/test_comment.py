"""Tests for PR comment posting functionality."""

import subprocess

import pytest
from click.testing import CliRunner

from vibediff.cli import _post_pr_comment, main


class TestPostPRComment:
    def test_success(self, monkeypatch):
        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert _post_pr_comment("42", "test body") is True
        assert calls[0] == ["gh", "pr", "comment", "42", "--body", "test body"]

    def test_failure(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, stderr="auth failed")

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert _post_pr_comment("42", "body") is False

    def test_gh_not_found(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert _post_pr_comment("42", "body") is False


class TestCommentFlag:
    def test_comment_requires_pr(self):
        runner = CliRunner()
        result = runner.invoke(main, ["review", "HEAD", "--comment"])
        assert result.exit_code != 0
        assert "--comment requires --pr" in result.output

    def test_comment_with_pr(self, tmp_path, monkeypatch):
        """Test that --comment generates markdown and calls gh pr comment."""
        import subprocess as sp

        monkeypatch.chdir(tmp_path)

        # Set up a git repo
        sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        sp.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
        sp.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)

        (tmp_path / "app.py").write_text("x = 1\n")
        sp.run(["git", "add", "."], cwd=tmp_path, check=True)
        sp.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

        (tmp_path / "app.py").write_text("x = 1\ny = 2\n")

        # Track calls to subprocess.run
        original_run = sp.run
        gh_calls = []

        def mock_run(cmd, **kwargs):
            if cmd[0] == "gh" and cmd[1] == "pr":
                if cmd[2] == "diff":
                    # Return a simple diff
                    return original_run(
                        ["git", "diff", "HEAD"], cwd=tmp_path, **kwargs
                    )
                if cmd[2] == "comment":
                    gh_calls.append(cmd)
                    return sp.CompletedProcess(cmd, 0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(sp, "run", mock_run)

        runner = CliRunner()
        result = runner.invoke(
            main, ["review", "123", "--pr", "--comment", "--no-fingerprint"]
        )
        assert result.exit_code == 0
        assert len(gh_calls) == 1
        assert gh_calls[0][2] == "comment"
        assert gh_calls[0][3] == "123"
        # Body should contain markdown
        assert "VibeDiff" in gh_calls[0][5]
