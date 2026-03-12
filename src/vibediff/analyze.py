from __future__ import annotations

import re
from dataclasses import dataclass, field

from vibediff.diff import FileDiff, Diff


@dataclass
class Finding:
    signal: str
    detail: str
    severity: float  # 0.0 to 1.0
    locations: list[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    ai_score: float  # 0-100, higher = more likely AI
    findings: list[Finding] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.ai_score >= 75:
            return "high"
        if self.ai_score >= 40:
            return "medium"
        return "low"


# --- comment pattern detection ---

# Comments that just restate what the code does
RESTATE_PATTERNS = [
    re.compile(r"#\s*(initialize|init|set up|setup|create|define|declare)\s+(the|a)\s+", re.I),
    re.compile(r"#\s*(import|load)\s+(the\s+)?(required|necessary|needed)", re.I),
    re.compile(r"#\s*(check|validate|verify)\s+(if|that|whether)\s+", re.I),
    re.compile(r"#\s*(return|send back)\s+(the|a)\s+", re.I),
    re.compile(r"#\s*(log|print|output)\s+(the|a|an)\s+", re.I),
    re.compile(r"#\s*(get|fetch|retrieve|query)\s+(the|a)\s+", re.I),
    re.compile(r"#\s*(update|modify|change|set)\s+(the|a)\s+", re.I),
    re.compile(r"#\s*(handle|process|parse)\s+(the|a)\s+", re.I),
]

# Section-header style comments AI loves
SECTION_HEADER = re.compile(r"#\s*-{3,}|#\s*={3,}|#\s*\*{3,}")

# Docstrings that restate function name
DOCSTRING_RESTATE = re.compile(
    r'"""'
    r"(Initialize|Create|Return|Get|Set|Update|Delete|Handle|Process|Validate|Check)"
    r"\s+(the|a|an)\s+",
    re.I,
)


def _score_comments(files: list[FileDiff]) -> tuple[float, list[Finding]]:
    findings: list[Finding] = []
    total_added = 0
    comment_lines = 0
    restate_count = 0
    section_headers = 0
    docstring_restates = 0

    for f in files:
        for line in f.added:
            stripped = line.strip()
            total_added += 1

            if stripped.startswith("#"):
                comment_lines += 1
                for pat in RESTATE_PATTERNS:
                    if pat.search(stripped):
                        restate_count += 1
                        break
                if SECTION_HEADER.match(stripped):
                    section_headers += 1

            if stripped.startswith('"""') or stripped.startswith("'''"):
                if DOCSTRING_RESTATE.search(stripped):
                    docstring_restates += 1

    if total_added == 0:
        return 0.0, findings

    comment_ratio = comment_lines / total_added

    # High comment ratio is suspicious
    if comment_ratio > 0.25:
        findings.append(Finding(
            signal="comment_density",
            detail=f"{comment_ratio:.0%} of added lines are comments (typical human code: 5-15%)",
            severity=min(comment_ratio / 0.4, 1.0),
        ))

    if restate_count >= 3:
        findings.append(Finding(
            signal="restating_comments",
            detail=f"{restate_count} comments that restate what the code does",
            severity=min(restate_count / 8, 1.0),
        ))

    if section_headers >= 2:
        findings.append(Finding(
            signal="section_headers",
            detail=f"{section_headers} section-divider comments (# ---, # ===)",
            severity=min(section_headers / 4, 1.0),
        ))

    if docstring_restates >= 2:
        findings.append(Finding(
            signal="docstring_restates",
            detail=f"{docstring_restates} docstrings that restate the function name",
            severity=min(docstring_restates / 5, 1.0),
        ))

    weights = [f.severity for f in findings]
    return (sum(weights) / max(len(weights), 1)) * 100, findings


# --- naming pattern detection ---

IDENTIFIER = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)*)\b")
CAMEL_IDENTIFIER = re.compile(r"\b([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)\b")
FUNC_DEF = re.compile(r"def\s+(\w+)")
CLASS_DEF = re.compile(r"class\s+(\w+)")
VAR_ASSIGN = re.compile(r"^(\s*)(\w+)\s*[=:]")


def _word_count(name: str) -> int:
    """Count words in a snake_case or camelCase identifier."""
    # snake_case
    if "_" in name:
        return len(name.split("_"))
    # camelCase — split on uppercase boundaries
    parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z]|$)", name)
    return max(len(parts), 1)


def _score_naming(files: list[FileDiff]) -> tuple[float, list[Finding]]:
    findings: list[Finding] = []
    func_names: list[str] = []
    var_names: list[str] = []

    for f in files:
        if f.language != "python":
            continue
        for line in f.added:
            m = FUNC_DEF.search(line)
            if m:
                func_names.append(m.group(1))
            m = VAR_ASSIGN.match(line)
            if m and not m.group(2).startswith("_") and m.group(2) not in ("self", "cls"):
                var_names.append(m.group(2))

    if not func_names and not var_names:
        return 0.0, findings

    # Check for verbose naming — AI loves 4+ word function names
    verbose_funcs = [n for n in func_names if _word_count(n) >= 4]
    if verbose_funcs and len(verbose_funcs) >= len(func_names) * 0.4:
        findings.append(Finding(
            signal="verbose_names",
            detail=f"{len(verbose_funcs)}/{len(func_names)} functions have 4+ word names",
            severity=min(len(verbose_funcs) / max(len(func_names), 1), 1.0),
            locations=verbose_funcs[:5],
        ))

    # Check for uniform name length — humans vary, AI is consistent
    if len(func_names) >= 4:
        lengths = [_word_count(n) for n in func_names]
        avg = sum(lengths) / len(lengths)
        variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
        if variance < 0.5 and avg >= 3:
            findings.append(Finding(
                signal="uniform_naming",
                detail=f"Function names are suspiciously uniform ({avg:.1f} words avg, variance {variance:.2f})",
                severity=0.6,
            ))

    # Check for absence of short variable names — humans use i, n, k, v, etc.
    if var_names:
        short_vars = [n for n in var_names if len(n) <= 2]
        short_ratio = len(short_vars) / len(var_names)
        if short_ratio < 0.05 and len(var_names) >= 10:
            findings.append(Finding(
                signal="no_short_vars",
                detail=f"No short variable names in {len(var_names)} variables (humans use i, k, v, etc.)",
                severity=0.5,
            ))

    weights = [f.severity for f in findings]
    return (sum(weights) / max(len(weights), 1)) * 100, findings


# --- burstiness / uniformity detection ---

def _line_complexity(line: str) -> float:
    """Rough token density of a line — operators, calls, nesting."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith('"""'):
        return 0.0
    score = 0.0
    score += stripped.count("(") + stripped.count(")")
    score += stripped.count("[") + stripped.count("]")
    score += stripped.count(".") * 0.5
    score += stripped.count(",") * 0.3
    score += len(stripped) / 40  # length contributes
    return score


def _score_burstiness(files: list[FileDiff]) -> tuple[float, list[Finding]]:
    findings: list[Finding] = []
    complexities: list[float] = []

    for f in files:
        for line in f.added:
            c = _line_complexity(line)
            if c > 0:
                complexities.append(c)

    if len(complexities) < 15:
        return 0.0, findings

    avg = sum(complexities) / len(complexities)
    if avg == 0:
        return 0.0, findings

    variance = sum((c - avg) ** 2 for c in complexities) / len(complexities)
    std_dev = variance ** 0.5
    cv = std_dev / avg  # coefficient of variation

    # Human code: CV typically 0.6-1.2 (high variation)
    # AI code: CV typically 0.2-0.5 (uniform)
    if cv < 0.45:
        severity = max(0.0, min((0.45 - cv) / 0.25, 1.0))
        findings.append(Finding(
            signal="low_burstiness",
            detail=f"Line complexity is unusually uniform (CV={cv:.2f}, human code typically >0.6)",
            severity=severity,
        ))

    return (sum(f.severity for f in findings) / max(len(findings), 1)) * 100, findings


# --- structural patterns ---

GUARD_CLAUSE = re.compile(r"if\s+\w+\s+is\s+None")
BROAD_EXCEPT = re.compile(r"except\s+(Exception|BaseException)\b")


def _score_structure(files: list[FileDiff]) -> tuple[float, list[Finding]]:
    findings: list[Finding] = []
    guard_count = 0
    broad_except_count = 0
    func_count = 0

    for f in files:
        if f.language != "python":
            continue
        for line in f.added:
            if FUNC_DEF.search(line):
                func_count += 1
            if GUARD_CLAUSE.search(line):
                guard_count += 1
            if BROAD_EXCEPT.search(line):
                broad_except_count += 1

    if func_count == 0:
        return 0.0, findings

    # Excessive guard clauses
    guard_ratio = guard_count / func_count
    if guard_ratio >= 1.0 and guard_count >= 3:
        findings.append(Finding(
            signal="excessive_guards",
            detail=f"{guard_count} 'is None' guards across {func_count} functions",
            severity=min(guard_ratio / 2, 1.0),
        ))

    # Broad exception handling
    if broad_except_count >= 2:
        findings.append(Finding(
            signal="broad_exceptions",
            detail=f"{broad_except_count} broad 'except Exception' blocks",
            severity=min(broad_except_count / 4, 1.0),
        ))

    weights = [f.severity for f in findings]
    return (sum(weights) / max(len(weights), 1)) * 100, findings


# --- main entry point ---

SIGNAL_WEIGHTS = {
    "comments": 0.30,
    "naming": 0.25,
    "burstiness": 0.25,
    "structure": 0.20,
}


def analyze_ai(diff: Diff) -> AnalysisReport:
    """Run all AI detection signals on a diff and return a scored report."""
    python_files = [f for f in diff.files if f.language == "python"]
    all_files = diff.files

    scores: dict[str, float] = {}
    all_findings: list[Finding] = []

    scores["comments"], findings = _score_comments(all_files)
    all_findings.extend(findings)

    scores["naming"], findings = _score_naming(python_files)
    all_findings.extend(findings)

    scores["burstiness"], findings = _score_burstiness(all_files)
    all_findings.extend(findings)

    scores["structure"], findings = _score_structure(python_files)
    all_findings.extend(findings)

    weighted = sum(scores[k] * SIGNAL_WEIGHTS[k] for k in SIGNAL_WEIGHTS)
    return AnalysisReport(ai_score=min(weighted, 100), findings=all_findings)
