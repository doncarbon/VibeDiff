from __future__ import annotations

import os

try:
    import anthropic
except ImportError:
    anthropic = None

MAX_DIFF_CHARS = 8000

SYSTEM_PROMPT = """\
You are VibeDiff, a code review tool that detects AI-generated code patterns, \
style drift, collaboration quality, and cross-language idiom contamination in PRs.

Given heuristic analysis results and the raw diff, write a 2-4 sentence summary \
of what happened in this PR. Focus on the most important finding. Be direct. \
Do not be sycophantic. Do not repeat the scores — interpret them."""


def synthesize(
    diff_text: str,
    analysis_json: dict,
    grade: str,
) -> str | None:
    """Call Claude to synthesize a natural-language review summary.

    Returns the summary text, or None if the API key is missing,
    the anthropic package isn't installed, or the call fails.
    """
    if anthropic is None:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    truncated = diff_text[:MAX_DIFF_CHARS]
    if len(diff_text) > MAX_DIFF_CHARS:
        truncated += "\n... (truncated)"

    user_msg = f"Grade: {grade}\n\nAnalysis:\n{_fmt(analysis_json)}\n\nDiff:\n```\n{truncated}\n```"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return resp.content[0].text
    except Exception:
        return None


def _fmt(d: dict, indent: int = 0) -> str:
    lines = []
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(_fmt(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}{k}: [{len(v)} items]")
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)
