from __future__ import annotations

import re
from dataclasses import dataclass, field

from vibediff.diff import Diff
from vibediff.fingerprint import Fingerprint, _word_count

FUNC_DEF = re.compile(r"^\s*def\s+(\w+)")
FUNC_DEF_FULL = re.compile(r"^\s*def\s+\w+\(([^)]*)\)(\s*->\s*\S+)?")
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")
CAMEL_CASE = re.compile(r"^[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$")
COMMENT_LINE = re.compile(r"^\s*#")
IMPORT_FROM = re.compile(r"^\s*from\s+\S+\s+import\s+")
IMPORT_BARE = re.compile(r"^\s*import\s+")
DOCSTRING_OPEN = re.compile(r'^\s*("""|\'\'\')')
EXCEPT_SPECIFIC = re.compile(r"^\s*except\s+(?!Exception\b|BaseException\b)\w+")
EXCEPT_BROAD = re.compile(r"^\s*except\s*(Exception|BaseException|\s*:)")
DECORATOR = re.compile(r"^\s*@\w+")


@dataclass
class DriftFinding:
    signal: str
    expected: str
    found: str
    severity: float


@dataclass
class DriftReport:
    drift_score: float  # 0-100
    findings: list[DriftFinding] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.drift_score >= 60:
            return "high"
        if self.drift_score >= 30:
            return "medium"
        return "low"


def _check_naming(diff: Diff, fp: Fingerprint) -> list[DriftFinding]:
    findings = []
    pr_funcs = []
    for f in diff.files:
        if f.language != "python":
            continue
        for line in f.added:
            m = FUNC_DEF.search(line)
            if m and not m.group(1).startswith("_"):
                pr_funcs.append(m.group(1))

    if len(pr_funcs) < 2:
        return findings

    # Check naming convention mismatch
    pr_snake = sum(1 for n in pr_funcs if SNAKE_CASE.match(n))
    pr_camel = sum(1 for n in pr_funcs if CAMEL_CASE.match(n))
    pr_snake_ratio = pr_snake / len(pr_funcs)
    pr_camel_ratio = pr_camel / len(pr_funcs)

    if fp.snake_case_ratio > 0.7 and pr_camel_ratio > 0.3:
        findings.append(DriftFinding(
            signal="naming_convention",
            expected=f"snake_case ({fp.snake_case_ratio:.0%} of codebase)",
            found=f"camelCase in {pr_camel}/{len(pr_funcs)} new functions",
            severity=min(pr_camel_ratio, 1.0),
        ))
    elif fp.camel_case_ratio > 0.7 and pr_snake_ratio > 0.3:
        findings.append(DriftFinding(
            signal="naming_convention",
            expected=f"camelCase ({fp.camel_case_ratio:.0%} of codebase)",
            found=f"snake_case in {pr_snake}/{len(pr_funcs)} new functions",
            severity=min(pr_snake_ratio, 1.0),
        ))

    # Check name verbosity drift
    if fp.avg_func_name_words > 0 and len(pr_funcs) >= 3:
        pr_avg = sum(_word_count(n) for n in pr_funcs) / len(pr_funcs)
        delta = abs(pr_avg - fp.avg_func_name_words)
        if delta >= 1.5:
            findings.append(DriftFinding(
                signal="name_verbosity",
                expected=f"{fp.avg_func_name_words:.1f} words per function name",
                found=f"{pr_avg:.1f} words per function name",
                severity=min(delta / 3, 1.0),
            ))

    return findings


def _check_comments(diff: Diff, fp: Fingerprint) -> list[DriftFinding]:
    findings = []
    pr_lines = 0
    pr_comments = 0

    for f in diff.files:
        for line in f.added:
            pr_lines += 1
            if COMMENT_LINE.match(line):
                pr_comments += 1

    if pr_lines < 10:
        return findings

    pr_ratio = pr_comments / pr_lines
    delta = pr_ratio - fp.comment_ratio

    # PR has significantly more comments than codebase
    if delta > 0.10 and pr_ratio > 0.15:
        findings.append(DriftFinding(
            signal="comment_density",
            expected=f"{fp.comment_ratio:.0%} comment density",
            found=f"{pr_ratio:.0%} comment density",
            severity=min(delta / 0.2, 1.0),
        ))
    # PR has significantly fewer comments
    elif delta < -0.10 and fp.comment_ratio > 0.15:
        findings.append(DriftFinding(
            signal="comment_density",
            expected=f"{fp.comment_ratio:.0%} comment density",
            found=f"{pr_ratio:.0%} comment density",
            severity=min(abs(delta) / 0.2, 1.0),
        ))

    return findings


def _check_func_length(diff: Diff, fp: Fingerprint) -> list[DriftFinding]:
    findings = []
    if fp.avg_func_length == 0:
        return findings

    # Measure function lengths in the diff (rough: count lines between def statements)
    pr_func_lengths = []
    for f in diff.files:
        if f.language != "python":
            continue
        current_start = None
        lines = f.added
        for i, line in enumerate(lines):
            if FUNC_DEF.search(line):
                if current_start is not None:
                    pr_func_lengths.append(i - current_start)
                current_start = i
        if current_start is not None:
            pr_func_lengths.append(len(lines) - current_start)

    if len(pr_func_lengths) < 2:
        return findings

    pr_avg = sum(pr_func_lengths) / len(pr_func_lengths)
    ratio = pr_avg / fp.avg_func_length if fp.avg_func_length > 0 else 1.0

    if ratio > 2.0:
        findings.append(DriftFinding(
            signal="function_length",
            expected=f"{fp.avg_func_length:.0f} lines avg",
            found=f"{pr_avg:.0f} lines avg ({ratio:.1f}x longer)",
            severity=min((ratio - 1) / 3, 1.0),
        ))
    elif ratio < 0.4 and fp.avg_func_length > 10:
        findings.append(DriftFinding(
            signal="function_length",
            expected=f"{fp.avg_func_length:.0f} lines avg",
            found=f"{pr_avg:.0f} lines avg ({ratio:.1f}x shorter)",
            severity=min((1 - ratio) / 0.6, 1.0),
        ))

    return findings


def _check_imports(diff: Diff, fp: Fingerprint) -> list[DriftFinding]:
    findings = []
    pr_from = 0
    pr_bare = 0

    for f in diff.files:
        if f.language != "python":
            continue
        for line in f.added:
            if IMPORT_FROM.match(line):
                pr_from += 1
            elif IMPORT_BARE.match(line):
                pr_bare += 1

    total = pr_from + pr_bare
    if total < 3:
        return findings

    pr_from_ratio = pr_from / total
    delta = abs(pr_from_ratio - fp.from_import_ratio)

    if delta > 0.4:
        expected_style = "from-imports" if fp.from_import_ratio > 0.5 else "bare imports"
        found_style = "from-imports" if pr_from_ratio > 0.5 else "bare imports"
        if expected_style != found_style:
            findings.append(DriftFinding(
                signal="import_style",
                expected=f"{expected_style} ({fp.from_import_ratio:.0%})",
                found=f"{found_style} ({pr_from_ratio:.0%})",
                severity=min(delta / 0.5, 1.0),
            ))

    return findings


def _check_error_handling(diff: Diff, fp: Fingerprint) -> list[DriftFinding]:
    findings = []
    if fp.specific_except_ratio == 0 and fp.try_except_ratio == 0:
        return findings

    pr_specific = 0
    pr_broad = 0
    for f in diff.files:
        if f.language != "python":
            continue
        for line in f.added:
            if EXCEPT_SPECIFIC.match(line):
                pr_specific += 1
            elif EXCEPT_BROAD.match(line):
                pr_broad += 1

    pr_total = pr_specific + pr_broad
    if pr_total < 2:
        return findings

    pr_specific_ratio = pr_specific / pr_total

    # Codebase uses specific exceptions but PR uses broad ones
    if fp.specific_except_ratio > 0.6 and pr_specific_ratio < 0.3:
        findings.append(DriftFinding(
            signal="error_handling",
            expected=f"specific exceptions ({fp.specific_except_ratio:.0%} of codebase)",
            found=f"broad exceptions ({pr_broad}/{pr_total} in PR)",
            severity=min((fp.specific_except_ratio - pr_specific_ratio) / 0.5, 1.0),
        ))

    return findings


def _check_type_annotations(diff: Diff, fp: Fingerprint) -> list[DriftFinding]:
    findings = []

    pr_params = 0
    pr_annotated = 0
    pr_funcs = 0
    pr_return_annotated = 0

    for f in diff.files:
        if f.language != "python":
            continue
        for line in f.added:
            fm = FUNC_DEF_FULL.match(line)
            if fm:
                pr_funcs += 1
                if fm.group(2):
                    pr_return_annotated += 1
                for param in fm.group(1).split(","):
                    param = param.strip()
                    if not param or param in ("self", "cls"):
                        continue
                    pr_params += 1
                    if ":" in param:
                        pr_annotated += 1

    if pr_params < 3:
        return findings

    pr_ratio = pr_annotated / pr_params

    # Codebase uses annotations but PR doesn't
    if fp.type_annotation_ratio > 0.6 and pr_ratio < 0.3:
        findings.append(DriftFinding(
            signal="type_annotations",
            expected=f"type hints ({fp.type_annotation_ratio:.0%} of params)",
            found=f"no type hints ({pr_annotated}/{pr_params} params)",
            severity=min((fp.type_annotation_ratio - pr_ratio) / 0.5, 1.0),
        ))
    # Codebase doesn't use annotations but PR does
    elif fp.type_annotation_ratio < 0.2 and pr_ratio > 0.7:
        findings.append(DriftFinding(
            signal="type_annotations",
            expected=f"no type hints ({fp.type_annotation_ratio:.0%} of params)",
            found=f"type hints on {pr_annotated}/{pr_params} params",
            severity=min((pr_ratio - fp.type_annotation_ratio) / 0.5, 1.0),
        ))

    return findings


def _check_decorators(diff: Diff, fp: Fingerprint) -> list[DriftFinding]:
    findings = []
    if fp.decorator_density == 0:
        return findings

    pr_decorators = 0
    pr_funcs = 0
    for f in diff.files:
        if f.language != "python":
            continue
        for line in f.added:
            if DECORATOR.match(line):
                pr_decorators += 1
            if FUNC_DEF.match(line):
                pr_funcs += 1

    if pr_funcs < 2:
        return findings

    pr_density = pr_decorators / pr_funcs
    ratio = pr_density / fp.decorator_density if fp.decorator_density > 0 else 0

    if ratio > 3.0 and pr_decorators >= 4:
        findings.append(DriftFinding(
            signal="decorator_density",
            expected=f"{fp.decorator_density:.1f} decorators/function",
            found=f"{pr_density:.1f} decorators/function ({ratio:.1f}x more)",
            severity=min((ratio - 1) / 4, 1.0),
        ))

    return findings


DRIFT_CHECKS = [
    _check_naming,
    _check_comments,
    _check_func_length,
    _check_imports,
    _check_error_handling,
    _check_type_annotations,
    _check_decorators,
]


def analyze_drift(diff: Diff, fp: Fingerprint) -> DriftReport:
    all_findings = []
    for check in DRIFT_CHECKS:
        all_findings.extend(check(diff, fp))

    if not all_findings:
        return DriftReport(drift_score=0)

    avg_severity = sum(f.severity for f in all_findings) / len(all_findings)
    coverage = min(len(all_findings) / len(DRIFT_CHECKS), 1.0)
    score = avg_severity * coverage * 100

    return DriftReport(drift_score=min(score, 100), findings=all_findings)
