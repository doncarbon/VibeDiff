# VibeDiff

AI-era code review. Detects AI-generated patterns, style drift, and collaboration quality in your PRs.

## Install

```bash
pip install vibediff
```

## Usage

```bash
vibediff review HEAD~1          # review last commit
vibediff review main..feature   # review branch diff
vibediff learn .                # learn codebase conventions
```

## License

MIT
