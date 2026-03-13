from __future__ import annotations

import re
from dataclasses import dataclass, field

from vibediff.diff import Diff, FileDiff

FUNC_DEF = re.compile(r"^\s*def\s+(\w+)")
TODO_PATTERN = re.compile(r"(?:#|//)\s*TODO", re.I)
GENERIC_NAMES = re.compile(r"^(data|result|output|response|value|item|obj|temp|tmp|ret|res|info)$")
GENERIC_TEST = re.compile(r"def\s+test_(function|method|case|it|thing|stuff|example)_?\d*\s*\(")
JS_GENERIC_TEST = re.compile(
    r"(?:it|test)\s*\(\s*['\"](?:should\s+)?(?:works?|tests?|does something|example|stuff|thing)\b",
    re.I,
)
VAR_ASSIGN = re.compile(r"^\s*(\w+)\s*=\s*")
JS_VAR_ASSIGN = re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*=")
PLACEHOLDER = re.compile(r"(pass\s*$|raise\s+NotImplementedError|\.\.\.\s*$)")
JS_PLACEHOLDER = re.compile(
    r"(throw\s+new\s+Error\s*\(\s*['\"](?:Not implemented|TODO|FIXME)['\"]|"
    r"//\s*TODO|"
    r"console\.log\s*\(\s*['\"](?:not implemented|todo)['\"])",
    re.I,
)


@dataclass
class CollabFinding:
    signal: str
    detail: str
    severity: float
    locations: list[str] = field(default_factory=list)


@dataclass
class CollabReport:
    collab_score: float  # 0-100, higher = better collaboration
    findings: list[CollabFinding] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.collab_score >= 70:
            return "good"
        if self.collab_score >= 40:
            return "mixed"
        return "poor"


def _check_todos(files: list[FileDiff]) -> list[CollabFinding]:
    findings = []
    count = 0
    todo_files: set[str] = set()
    for f in files:
        for line in f.added:
            if TODO_PATTERN.search(line):
                count += 1
                todo_files.add(f.path)

    if count >= 2:
        findings.append(CollabFinding(
            signal="unresolved_todos",
            detail=f"{count} TODO comments left in",
            severity=min(count / 5, 1.0),
            locations=sorted(todo_files)[:5],
        ))
    return findings


def _check_generic_names(files: list[FileDiff]) -> list[CollabFinding]:
    findings = []
    generic_count = 0
    total_vars = 0
    generic_files: set[str] = set()

    for f in files:
        if f.language == "python":
            for line in f.added:
                m = VAR_ASSIGN.match(line)
                if m:
                    name = m.group(1)
                    if name in ("self", "cls", "_"):
                        continue
                    total_vars += 1
                    if GENERIC_NAMES.match(name):
                        generic_count += 1
                        generic_files.add(f.path)
        elif f.language in ("javascript", "typescript"):
            for line in f.added:
                m = JS_VAR_ASSIGN.match(line)
                if m:
                    name = m.group(1)
                    total_vars += 1
                    if GENERIC_NAMES.match(name):
                        generic_count += 1
                        generic_files.add(f.path)

    if total_vars >= 5 and generic_count / total_vars > 0.3:
        findings.append(CollabFinding(
            signal="generic_names",
            detail=f"{generic_count}/{total_vars} variables have generic names (data, result, output, etc.)",
            severity=min(generic_count / total_vars / 0.5, 1.0),
            locations=sorted(generic_files)[:5],
        ))
    return findings


def _check_generic_tests(files: list[FileDiff]) -> list[CollabFinding]:
    findings = []
    count = 0
    test_files: set[str] = set()
    for f in files:
        for line in f.added:
            if GENERIC_TEST.search(line) or JS_GENERIC_TEST.search(line):
                count += 1
                test_files.add(f.path)

    if count >= 2:
        findings.append(CollabFinding(
            signal="generic_tests",
            detail=f"{count} test functions with generic names (test_function_1, test_method_2, etc.)",
            severity=min(count / 4, 1.0),
            locations=sorted(test_files)[:5],
        ))
    return findings


def _check_placeholders(files: list[FileDiff]) -> list[CollabFinding]:
    findings = []
    count = 0
    stub_files: set[str] = set()
    for f in files:
        if f.language == "python":
            for line in f.added:
                if PLACEHOLDER.search(line.strip()):
                    count += 1
                    stub_files.add(f.path)
        elif f.language in ("javascript", "typescript"):
            for line in f.added:
                if JS_PLACEHOLDER.search(line.strip()):
                    count += 1
                    stub_files.add(f.path)

    if count >= 3:
        findings.append(CollabFinding(
            signal="placeholders",
            detail=f"{count} placeholder/stub lines (pass, ..., NotImplementedError)",
            severity=min(count / 6, 1.0),
            locations=sorted(stub_files)[:5],
        ))
    return findings


def _check_uniformity(files: list[FileDiff]) -> list[CollabFinding]:
    """Flag when all files in a large PR have suspiciously uniform style — no human editing trace."""
    findings = []
    if len(files) < 3:
        return findings

    # Check if all files have similar comment ratios (AI dumps are uniform)
    ratios = []
    for f in files:
        total = len(f.added)
        if total < 5:
            continue
        comments = sum(1 for line in f.added if line.strip().startswith("#"))
        ratios.append(comments / total)

    if len(ratios) < 3:
        return findings

    avg = sum(ratios) / len(ratios)
    if avg == 0:
        return findings

    variance = sum((r - avg) ** 2 for r in ratios) / len(ratios)

    # Very low variance across many files = no human editing
    if variance < 0.005 and avg > 0.05:
        findings.append(CollabFinding(
            signal="uniform_style",
            detail=f"Comment density is identical across {len(ratios)} files (variance {variance:.4f}) — no human editing trace",
            severity=0.7,
        ))

    return findings


def analyze_collaboration(diff: Diff) -> CollabReport:
    all_findings: list[CollabFinding] = []

    all_findings.extend(_check_todos(diff.files))
    all_findings.extend(_check_generic_names(diff.files))
    all_findings.extend(_check_generic_tests(diff.files))
    all_findings.extend(_check_placeholders(diff.files))
    all_findings.extend(_check_uniformity(diff.files))

    if not all_findings:
        return CollabReport(collab_score=100)

    # More issues = lower collaboration score
    avg_severity = sum(f.severity for f in all_findings) / len(all_findings)
    coverage = min(len(all_findings) / 5, 1.0)
    penalty = avg_severity * coverage * 100
    score = max(0, 100 - penalty)

    return CollabReport(collab_score=score, findings=all_findings)
