# vibediff

Knows when a PR doesn't belong in your codebase.

vibediff learns how your project writes code — naming conventions, structure, patterns — then flags PRs that don't match. It catches style drift, cross-language idiom bleed (Java patterns in Python, etc.), and scores whether the author actually reviewed AI output or just committed it raw.

## Install

```
pip install vibediff
```

## Usage

```
vibediff review HEAD~3
vibediff review main..feature
```

## License

MIT
