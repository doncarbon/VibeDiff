"""Tests for the LLM synthesis layer."""

import os
from unittest.mock import MagicMock, patch

from vibediff.synthesize import MAX_DIFF_CHARS, SYSTEM_PROMPT, _fmt, synthesize

SAMPLE_ANALYSIS = {
    "grade": "C",
    "ai_detection": {"score": 75, "label": "high", "findings": []},
    "collaboration": {"score": 60, "label": "mixed", "findings": []},
}


def test_returns_none_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = synthesize("diff text", SAMPLE_ANALYSIS, "C")
    assert result is None


def test_returns_none_without_anthropic_package():
    import vibediff.synthesize as mod
    original = mod.anthropic
    mod.anthropic = None
    try:
        result = synthesize("diff text", SAMPLE_ANALYSIS, "C")
        assert result is None
    finally:
        mod.anthropic = original


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
def test_calls_claude_with_correct_params():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text="This PR looks AI-generated.")]
    mock_client.messages.create.return_value = mock_resp

    with patch("vibediff.synthesize.anthropic") as mock_mod:
        mock_mod.Anthropic.return_value = mock_client
        result = synthesize("some diff", SAMPLE_ANALYSIS, "C")

    assert result == "This PR looks AI-generated."
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"
    assert call_kwargs["system"] == SYSTEM_PROMPT
    assert "Grade: C" in call_kwargs["messages"][0]["content"]


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
def test_truncates_long_diffs():
    long_diff = "x" * (MAX_DIFF_CHARS + 1000)
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text="Summary.")]
    mock_client.messages.create.return_value = mock_resp

    with patch("vibediff.synthesize.anthropic") as mock_mod:
        mock_mod.Anthropic.return_value = mock_client
        synthesize(long_diff, SAMPLE_ANALYSIS, "C")

    msg = mock_client.messages.create.call_args[1]["messages"][0]["content"]
    assert "truncated" in msg
    assert len(msg) < MAX_DIFF_CHARS + 500


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
def test_returns_none_on_api_error():
    with patch("vibediff.synthesize.anthropic") as mock_mod:
        mock_mod.Anthropic.return_value.messages.create.side_effect = RuntimeError("boom")
        result = synthesize("diff", SAMPLE_ANALYSIS, "C")
    assert result is None


def test_fmt_formats_nested_dict():
    d = {"grade": "B", "ai": {"score": 50, "findings": [1, 2]}}
    text = _fmt(d)
    assert "grade: B" in text
    assert "score: 50" in text
    assert "[2 items]" in text
