from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from vibediff.diff import LANG_BY_EXT

FUNC_DEF = re.compile(r"^\s*def\s+(\w+)")
FUNC_DEF_FULL = re.compile(r"^\s*def\s+\w+\(([^)]*)\)(\s*->\s*\S+)?")
CLASS_DEF = re.compile(r"^\s*class\s+(\w+)")
IMPORT_FROM = re.compile(r"^\s*from\s+\S+\s+import\s+")
IMPORT_BARE = re.compile(r"^\s*import\s+")
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")
CAMEL_CASE = re.compile(r"^[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$")
COMMENT_LINE = re.compile(r"^\s*#")
DOCSTRING_OPEN = re.compile(r'^\s*("""|\'\'\')')
TRY_BLOCK = re.compile(r"^\s*try\s*:")
EXCEPT_SPECIFIC = re.compile(r"^\s*except\s+(?!Exception\b|BaseException\b)\w+")
EXCEPT_BROAD = re.compile(r"^\s*except\s*(Exception|BaseException|\s*:)")
DECORATOR = re.compile(r"^\s*@\w+")

# Directories to always skip
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".eggs", "*.egg-info",
}


@dataclass
class Fingerprint:
    """Snapshot of how a codebase writes code."""
    files_scanned: int = 0
    total_lines: int = 0

    # naming
    func_names: list[str] = field(default_factory=list)
    snake_case_ratio: float = 0.0
    camel_case_ratio: float = 0.0
    avg_func_name_words: float = 0.0

    # comments
    comment_ratio: float = 0.0

    # structure
    avg_func_length: float = 0.0
    func_lengths: list[int] = field(default_factory=list)

    # imports
    from_import_ratio: float = 0.0

    # docstrings
    docstring_ratio: float = 0.0

    # error handling
    try_except_ratio: float = 0.0        # % of functions that use try/except
    specific_except_ratio: float = 0.0   # % of except blocks naming a specific exception

    # type annotations
    type_annotation_ratio: float = 0.0   # % of function params with type hints
    return_annotation_ratio: float = 0.0 # % of functions with return type annotations

    # decorators
    decorator_density: float = 0.0       # decorators per function


def _word_count(name: str) -> int:
    if "_" in name:
        return len(name.split("_"))
    parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z]|$)", name)
    return max(len(parts), 1)


def _iter_files(root: str) -> list[Path]:
    """Walk the repo and collect source files we can analyze."""
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in LANG_BY_EXT:
                results.append(Path(dirpath) / fname)
    return results


def scan(root: str, languages: set[str] | None = None) -> Fingerprint:
    """Scan a codebase and build a style fingerprint."""
    fp = Fingerprint()
    all_funcs: list[str] = []
    total_lines = 0
    comment_lines = 0
    from_imports = 0
    bare_imports = 0
    func_lengths: list[int] = []
    funcs_with_docstring = 0
    total_funcs = 0
    funcs_with_try = 0
    except_specific = 0
    except_total = 0
    params_with_annotation = 0
    params_total = 0
    funcs_with_return_annotation = 0
    decorator_count = 0

    for path in _iter_files(root):
        ext = path.suffix.lower()
        lang = LANG_BY_EXT.get(ext, "unknown")
        if languages and lang not in languages:
            continue

        try:
            lines = path.read_text(errors="replace").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        fp.files_scanned += 1
        total_lines += len(lines)

        current_func_start: int | None = None
        current_func_has_try = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            if COMMENT_LINE.match(line):
                comment_lines += 1

            if IMPORT_FROM.match(line):
                from_imports += 1
            elif IMPORT_BARE.match(line):
                bare_imports += 1

            if DECORATOR.match(line):
                decorator_count += 1

            m = FUNC_DEF.match(line)
            if m:
                # close previous function
                if current_func_start is not None:
                    func_lengths.append(i - current_func_start)
                    if current_func_has_try:
                        funcs_with_try += 1

                name = m.group(1)
                if not name.startswith("_"):
                    all_funcs.append(name)
                total_funcs += 1
                current_func_start = i
                current_func_has_try = False

                # type annotations
                fm = FUNC_DEF_FULL.match(line)
                if fm:
                    params_str = fm.group(1)
                    if fm.group(2):
                        funcs_with_return_annotation += 1
                    for param in params_str.split(","):
                        param = param.strip()
                        if not param or param in ("self", "cls"):
                            continue
                        params_total += 1
                        if ":" in param:
                            params_with_annotation += 1

                # check next non-empty line for docstring
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j].strip():
                        if DOCSTRING_OPEN.match(lines[j]):
                            funcs_with_docstring += 1
                        break

            if TRY_BLOCK.match(line):
                current_func_has_try = True

            if EXCEPT_SPECIFIC.match(line):
                except_specific += 1
                except_total += 1
            elif EXCEPT_BROAD.match(line):
                except_total += 1

        # close last function
        if current_func_start is not None:
            func_lengths.append(len(lines) - current_func_start)
            if current_func_has_try:
                funcs_with_try += 1

    fp.total_lines = total_lines
    fp.func_names = all_funcs

    if all_funcs:
        snake = sum(1 for n in all_funcs if SNAKE_CASE.match(n))
        camel = sum(1 for n in all_funcs if CAMEL_CASE.match(n))
        fp.snake_case_ratio = snake / len(all_funcs)
        fp.camel_case_ratio = camel / len(all_funcs)
        fp.avg_func_name_words = sum(_word_count(n) for n in all_funcs) / len(all_funcs)

    if total_lines > 0:
        fp.comment_ratio = comment_lines / total_lines

    if func_lengths:
        fp.func_lengths = func_lengths
        fp.avg_func_length = sum(func_lengths) / len(func_lengths)

    total_imports = from_imports + bare_imports
    if total_imports > 0:
        fp.from_import_ratio = from_imports / total_imports

    if total_funcs > 0:
        fp.docstring_ratio = funcs_with_docstring / total_funcs
        fp.try_except_ratio = funcs_with_try / total_funcs
        fp.decorator_density = decorator_count / total_funcs
        fp.return_annotation_ratio = funcs_with_return_annotation / total_funcs

    if except_total > 0:
        fp.specific_except_ratio = except_specific / except_total

    if params_total > 0:
        fp.type_annotation_ratio = params_with_annotation / params_total

    return fp
