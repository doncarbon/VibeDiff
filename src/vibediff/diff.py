from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from unidiff import PatchSet

LANG_BY_EXT: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript", ".java": "java", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".cpp": "cpp", ".c": "c", ".cs": "csharp", ".php": "php", ".swift": "swift",
    ".kt": "kotlin", ".scala": "scala", ".sh": "shell", ".bash": "shell", ".zsh": "shell",
}


def detect_language(filepath: str) -> str:
    return LANG_BY_EXT.get(Path(filepath).suffix.lower(), "unknown")


@dataclass
class Hunk:
    source_start: int
    source_length: int
    target_start: int
    target_length: int
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    language: str
    hunks: list[Hunk] = field(default_factory=list)
    is_new: bool = False
    is_deleted: bool = False
    is_renamed: bool = False
    old_path: str | None = None

    @property
    def added(self) -> list[str]:
        return [line for h in self.hunks for line in h.added]

    @property
    def removed(self) -> list[str]:
        return [line for h in self.hunks for line in h.removed]


@dataclass
class Diff:
    files: list[FileDiff] = field(default_factory=list)
    base_ref: str | None = None
    head_ref: str | None = None

    @property
    def languages(self) -> set[str]:
        return {f.language for f in self.files if f.language != "unknown"}


def _run_git_diff(target: str) -> str:
    cmd = ["git", "diff", "--cached"] if target == "staged" else ["git", "diff", target]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"git diff failed: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("git not found", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def parse_diff(raw: str) -> Diff:
    if not raw.strip():
        return Diff()

    files: list[FileDiff] = []
    for pf in PatchSet(raw):
        hunks = []
        for h in pf:
            hunks.append(Hunk(
                source_start=h.source_start,
                source_length=h.source_length,
                target_start=h.target_start,
                target_length=h.target_length,
                added=[str(ln.value) for ln in h if ln.is_added],
                removed=[str(ln.value) for ln in h if ln.is_removed],
                context=[str(ln.value) for ln in h if ln.is_context],
            ))
        files.append(FileDiff(
            path=pf.path,
            language=detect_language(pf.path),
            hunks=hunks,
            is_new=pf.is_added_file,
            is_deleted=pf.is_removed_file,
            is_renamed=pf.is_rename,
            old_path=pf.source_file if pf.is_rename else None,
        ))
    return Diff(files=files)


def diff_from_ref(target: str) -> Diff:
    raw = _run_git_diff(target)
    d = parse_diff(raw)
    d.head_ref = target
    return d
