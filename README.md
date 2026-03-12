# VibeDiff

AI agents write code that compiles, passes tests, and feels completely foreign in your codebase. It works — but it doesn't *fit*. Your naming is snake_case, the PR is camelCase. Your project uses properties, the PR is full of getter/setter methods straight out of a Java textbook. The author committed 500 lines without changing a single AI-generated variable name.

VibeDiff learns how your project actually writes code, then tells you when a PR doesn't match.

## What it catches

- **Style drift** — your codebase uses one set of conventions, the PR uses another
- **Idiom contamination** — AI bleeds patterns from other languages into your code (Java-style Python, Go-style error handling in JS, etc.)
- **Raw AI dumps** — 500 lines committed with zero human editing, generic variable names, TODO placeholders left in

## How it works

VibeDiff runs 4 analyzers on every diff:

**AI Detection** (0-100) — heuristic signals that code was AI-generated:
- Comment patterns (restating code, section headers, excessive density)
- Naming patterns (verbose 4+ word names, uniform naming, no short vars)
- Burstiness (AI has uniform line complexity; humans vary wildly)
- Structural patterns (excessive `is None` guards, broad `except Exception`)

**Style Drift** (0-100) — how much the diff deviates from your codebase conventions:
- Naming convention mismatch (camelCase in a snake_case codebase)
- Comment density deviation from baseline
- Function length drift (2x longer or 0.4x shorter than average)
- Import style mismatch (bare imports vs from-imports)

Run `vibediff learn` first to build a fingerprint of your codebase conventions.

**Collaboration Quality** (0-100) — signs the human didn't actually review the AI output:
- Unresolved TODO comments left in
- Generic variable names (data, result, output, value)
- Generic test names (test_function_1, test_method_2)
- Placeholder stubs (pass, ..., NotImplementedError)
- Uniform comment density across files (no human editing trace)

**Idiom Contamination** (0-100) — AI bleeding patterns from other languages:
- Java in Python: getter/setter methods, Interface/Abstract class naming
- Go in Python: error-return patterns (`return data, err`)
- C/C++ in Python: `== None` instead of `is None`
- JavaScript in Python: callback parameters

## Install

```
pip install vibediff
```

## Usage

```bash
# Review last commit
vibediff review HEAD~1

# Review a range
vibediff review main..feature

# Review a GitHub PR (requires gh CLI)
vibediff review --pr 42

# Learn your codebase conventions first (enables drift detection)
vibediff learn

# Skip drift analysis
vibediff review HEAD~1 --no-fingerprint

# JSON output (for CI pipelines)
vibediff review HEAD~1 --format json

# Markdown output (for PR comments)
vibediff review HEAD~1 --format md
```

Example output:

```
╭──────────────────────── VibeDiff ────────────────────────╮
│ 3 file(s)  +180 -12  AI: 58  Drift: 42                  │
╰──────────────────────────────────────────────────────────╯

AI Detection  58/100 (medium)
  restating_comments    4 comments that restate the code       ███░░
  verbose_names         3/5 functions have 4+ word names       ██░░░
  low_burstiness        CV 0.31 (expected >0.6)                ██░░░

Style Drift  42/100 (medium)
  naming_convention     expected snake_case, got camelCase     ███░░
  comment_density       expected 8%, got 22%                   ██░░░

Collaboration  65/100 (mixed)
  unresolved_todos      3 TODO comments left in                ██░░░
  generic_names         4/12 variables have generic names      ██░░░

Idiom Contamination  40/100 (medium)
  getter_setter         3 getter/setter methods [java]         ██░░░
  error_return_pattern  4 Go-style error returns [go]          ██░░░
```

## GitHub Action

Add VibeDiff to your PR workflow:

```yaml
# .github/workflows/vibediff.yml
name: VibeDiff
on:
  pull_request:

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

The action posts a markdown report to the PR's job summary. To enable style drift detection, commit a fingerprint and pass it:

```yaml
      - uses: doncarbon/VibeDiff@main
        with:
          fingerprint: .vibediff-cache/fingerprint.json
```

## Author

[Hamza](https://x.com/hamzayne)

## License

MIT
