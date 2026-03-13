<div align="center">

# VibeDiff

**What changed, who wrote it, and does it belong.**

[![PyPI](https://img.shields.io/pypi/v/vibediff?color=blue)](https://pypi.org/project/vibediff/)
[![Python](https://img.shields.io/pypi/pyversions/vibediff)](https://pypi.org/project/vibediff/)
[![License](https://img.shields.io/github/license/doncarbon/VibeDiff)](LICENSE)

</div>

---

AI agents write code that compiles, passes tests, and feels completely foreign in your codebase. It works — but it doesn't *fit*. Your naming is snake_case, the PR is camelCase. Your project uses properties, the PR is full of getter/setter methods straight out of a Java textbook. The author committed 500 lines without changing a single AI-generated variable name.

VibeDiff learns how your project actually writes code, then tells you when a PR doesn't match.

```
╭──────────────────────────────── VibeDiff ─────────────────────────────────╮
│                                                                           │
│  ████      3 file(s)  +180  -12                                           │
│  ██ ██                                                                    │
│  ██  ██      AI Detection           █████████░░░░░░      58    medium     │
│  ██ ██       Style Drift            ██████░░░░░░░░░      42    medium     │
│  ████        Collaboration          ██████████░░░░░      65    mixed      │
│              Idiom Contamination    ██████░░░░░░░░░      40    medium     │
│                                                                           │
╰──────────────────────────────────────────────────────────────────────────╯

──────────────── AI Detection  58/100 (medium) ─────────────────
  restating_comments    4 comments that restate the code  ███░░
  verbose_names         3/5 functions have 4+ word names  ██░░░
  low_burstiness        CV 0.31 (expected >0.6)           ██░░░

────────────────── Style Drift  42/100 (medium) ────────────────
  naming_convention     expected snake_case, got camelCase ███░░
  comment_density       expected 8%, got 22%               ██░░░

─────────────── Collaboration  65/100 (mixed) ──────────────────
  unresolved_todos      3 TODO comments left in            ██░░░
  generic_names         4/12 variables have generic names  ██░░░

──────────── Idiom Contamination  40/100 (medium) ──────────────
  getter_setter         3 getter/setter methods [java]     ███░░
  error_return_pattern  4 Go-style error returns [go]      ██░░░
```

## Install

```
pip install vibediff
```

Optional extras:

```bash
pip install "vibediff[llm]"   # Claude API synthesis
pip install "vibediff[mcp]"   # MCP server for AI editors
pip install "vibediff[all]"   # everything
```

## Usage

```bash
vibediff review HEAD~1              # review last commit
vibediff review main..feature       # review a range
vibediff review --pr 42             # review a GitHub PR (requires gh CLI)
vibediff learn                      # learn your codebase conventions
vibediff review HEAD~1 --format json  # JSON output for CI
vibediff review HEAD~1 --format md    # markdown output for PR comments
vibediff review --synthesize        # add Claude-powered natural language summary
vibediff serve                      # start MCP tool server
```

## What it does

Every diff gets a letter grade (A-F) from 4 analyzers:

| Analyzer | What it finds |
|---|---|
| **AI Detection** | Restating comments, verbose naming, uniform line complexity, excessive `is None` guards, broad exceptions |
| **Style Drift** | Naming convention mismatch, comment density deviation, function length drift, import style, type annotation drift, error handling style, decorator density |
| **Collaboration** | Unresolved TODOs, generic variable names, placeholder stubs, uniform style across files |
| **Idiom Contamination** | Java getters in Python, Go error-returns, C-style null checks, JS callback patterns |

Style Drift requires a fingerprint — run `vibediff learn` in your repo first. The fingerprint captures naming conventions, comment density, function lengths, import style, type annotation usage, error handling patterns, and decorator density.

## LLM Synthesis

Add `--synthesize` to get a Claude-powered natural language summary of the review:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
vibediff review HEAD~1 --synthesize
```

Requires `pip install "vibediff[llm]"`. Gracefully degrades — if the API key is missing or the package isn't installed, everything else still works.

## MCP Server

VibeDiff ships as an MCP tool server so AI editors (Claude Code, Cursor, etc.) can call it directly:

```bash
vibediff serve
```

Exposes two tools: `review` and `learn`. Configure in your editor's MCP settings:

```json
{
  "mcpServers": {
    "vibediff": {
      "command": "vibediff",
      "args": ["serve"]
    }
  }
}
```

Requires `pip install "vibediff[mcp]"`.

## GitHub Action

```yaml
# .github/workflows/vibediff.yml
name: VibeDiff
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: doncarbon/VibeDiff@main
```

To enable drift detection, commit your fingerprint and pass it:

```yaml
      - uses: doncarbon/VibeDiff@main
        with:
          fingerprint: .vibediff-cache/fingerprint.json
```

To enable LLM synthesis, pass your Anthropic API key:

```yaml
      - uses: doncarbon/VibeDiff@main
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

---

<div align="center">

Built by [Hamza](https://x.com/hamzayne) · MIT License

</div>
