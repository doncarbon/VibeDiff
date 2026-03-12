"""Core data models for VibeDiff's diff pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown",
}


def detect_language(filepath: str) -> str:
    """Detect programming language from file extension."""
    suffix = Path(filepath).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(suffix, "unknown")


@dataclass
class DiffHunk:
    """A single hunk within a diff file."""

    source_start: int
    source_length: int
    target_start: int
    target_length: int
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)


@dataclass
class DiffFile:
    """A single file within a diff."""

    path: str
    language: str
    hunks: list[DiffHunk] = field(default_factory=list)
    is_new: bool = False
    is_deleted: bool = False
    is_renamed: bool = False
    old_path: str | None = None

    @property
    def added_lines(self) -> list[str]:
        """All added lines across all hunks."""
        lines = []
        for hunk in self.hunks:
            lines.extend(hunk.added_lines)
        return lines

    @property
    def removed_lines(self) -> list[str]:
        """All removed lines across all hunks."""
        lines = []
        for hunk in self.hunks:
            lines.extend(hunk.removed_lines)
        return lines

    @property
    def total_added(self) -> int:
        return len(self.added_lines)

    @property
    def total_removed(self) -> int:
        return len(self.removed_lines)


@dataclass
class PatchContext:
    """The full parsed diff — input to all analyzers."""

    files: list[DiffFile] = field(default_factory=list)
    base_ref: str | None = None
    head_ref: str | None = None

    @property
    def total_added(self) -> int:
        return sum(f.total_added for f in self.files)

    @property
    def total_removed(self) -> int:
        return sum(f.total_removed for f in self.files)

    @property
    def languages(self) -> set[str]:
        return {f.language for f in self.files if f.language != "unknown"}
