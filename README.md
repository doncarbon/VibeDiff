# VibeDiff

AI agents write code that compiles, passes tests, and feels completely foreign in your codebase. It works — but it doesn't *fit*. Your naming is snake_case, the PR is camelCase. Your project uses properties, the PR is full of getter/setter methods straight out of a Java textbook. The author committed 500 lines without changing a single AI-generated variable name.

VibeDiff learns how your project actually writes code, then tells you when a PR doesn't match.

## What it catches

- **Style drift** — your codebase uses one set of conventions, the PR uses another
- **Idiom contamination** — AI bleeds patterns from other languages into your code (Java-style Python, Go-style error handling in JS, etc.)
- **Raw AI dumps** — 500 lines committed with zero human editing, generic variable names, TODO placeholders left in

## What it detects right now

VibeDiff analyzes diffs for AI-generated code patterns across 4 signal categories:

- **Comment patterns** — over-commenting, comments that restate the code, section-divider comments, docstrings that restate function names
- **Naming patterns** — verbose 4+ word function names, suspiciously uniform naming, absence of short variable names humans naturally use
- **Burstiness** — AI code has uniform line complexity; human code varies wildly line to line
- **Structural patterns** — excessive `is None` guards, broad `except Exception` blocks

Each signal produces a severity score. The weighted result gives an overall AI probability score from 0-100.

## Install

```
pip install vibediff
```

## Usage

```
vibediff review HEAD~1
vibediff review HEAD~5
vibediff review main..feature
```

Example output:

```
╭──────────────────────── VibeDiff ────────────────────────╮
│ 1 file(s)  +58 -0  AI score: 42/100 (medium)            │
╰──────────────────────────────────────────────────────────╯
Signal                Detail                                    Severity
excessive_guards      3 'is None' guards across 2 functions     █████
restating_comments    4 comments that restate what the code does ██░░░
verbose_names         1/2 functions have 4+ word names          ██░░░
no_short_vars         No short variable names in 10 variables   ██░░░
```

## Author

[Hamza](https://x.com/hamzayne)

## License

MIT
