"""Parse git diffs into VibeDiff's internal models."""

from __future__ import annotations

import subprocess
import sys

from unidiff import PatchSet

from vibediff.input.models import DiffFile, DiffHunk, PatchContext, detect_language


def run_git_diff(target: str) -> str:
    """Run git diff and return raw unified diff output."""
    if ".." in target:
        # Branch comparison: main..feature
        cmd = ["git", "diff", target]
    elif target == "staged":
        cmd = ["git", "diff", "--cached"]
    else:
        # Ref-based: HEAD~3, a1b2c3d, etc.
        cmd = ["git", "diff", target]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: git is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)

    return result.stdout


def parse_unified_diff(raw_diff: str) -> PatchContext:
    """Parse raw unified diff text into a PatchContext."""
    if not raw_diff.strip():
        return PatchContext()

    patch_set = PatchSet(raw_diff)
    files: list[DiffFile] = []

    for patched_file in patch_set:
        path = patched_file.path
        language = detect_language(path)

        hunks: list[DiffHunk] = []
        for hunk in patched_file:
            added = [str(line.value) for line in hunk if line.is_added]
            removed = [str(line.value) for line in hunk if line.is_removed]
            context = [str(line.value) for line in hunk if line.is_context]

            hunks.append(
                DiffHunk(
                    source_start=hunk.source_start,
                    source_length=hunk.source_length,
                    target_start=hunk.target_start,
                    target_length=hunk.target_length,
                    added_lines=added,
                    removed_lines=removed,
                    context_lines=context,
                )
            )

        diff_file = DiffFile(
            path=path,
            language=language,
            hunks=hunks,
            is_new=patched_file.is_added_file,
            is_deleted=patched_file.is_removed_file,
            is_renamed=patched_file.is_rename,
            old_path=patched_file.source_file if patched_file.is_rename else None,
        )
        files.append(diff_file)

    return PatchContext(files=files)


def parse_git_diff(target: str) -> PatchContext:
    """Run git diff for a target and parse the result."""
    raw = run_git_diff(target)
    patch = parse_unified_diff(raw)
    patch.head_ref = target
    return patch
