from __future__ import annotations

import re
from dataclasses import dataclass, field

from vibediff.diff import Diff, FileDiff


@dataclass
class IdiomFinding:
    signal: str
    source_lang: str
    detail: str
    severity: float
    locations: list[str] = field(default_factory=list)


@dataclass
class IdiomReport:
    idiom_score: float  # 0-100, higher = more contamination
    findings: list[IdiomFinding] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.idiom_score >= 60:
            return "high"
        if self.idiom_score >= 25:
            return "medium"
        return "low"


# --- Java patterns in Python ---

GETTER_SETTER = re.compile(r"def\s+(get|set)_?([A-Z]\w+)\s*\(self")
FACTORY_METHOD = re.compile(r"def\s+create_?\w*\s*\(cls\)|@classmethod\s*\n\s*def\s+create")
INTERFACE_ABUSE = re.compile(r"class\s+\w*(Interface|Abstract|Base)\w*\s*(\(.*ABC.*\))?:")
STRINGBUILDER = re.compile(r"(\w+)\s*\+=\s*['\"]")  # string concatenation in loop
BOOLEAN_GETTER = re.compile(r"def\s+is_\w+\s*\(self\)\s*->\s*bool")


def _java_in_python(files: list[FileDiff]) -> list[IdiomFinding]:
    findings = []

    getters_setters = []
    for f in files:
        if f.language != "python":
            continue
        for line in f.added:
            m = GETTER_SETTER.search(line)
            if m:
                getters_setters.append(f"{m.group(1)}_{m.group(2)}")

    if len(getters_setters) >= 2:
        findings.append(IdiomFinding(
            signal="getter_setter",
            source_lang="java",
            detail=f"{len(getters_setters)} getter/setter methods — use @property instead",
            severity=min(len(getters_setters) / 4, 1.0),
            locations=getters_setters[:4],
        ))

    # Interface/Abstract class naming
    interface_count = 0
    for f in files:
        if f.language != "python":
            continue
        for line in f.added:
            if INTERFACE_ABUSE.search(line):
                interface_count += 1

    if interface_count >= 2:
        findings.append(IdiomFinding(
            signal="interface_naming",
            source_lang="java",
            detail=f"{interface_count} classes named *Interface/*Abstract — not Pythonic",
            severity=min(interface_count / 3, 1.0),
        ))

    return findings


# --- Go patterns in Python ---

ERR_RETURN = re.compile(r"return\s+\w+\s*,\s*(None|err|error)\b")
ERR_CHECK = re.compile(r"if\s+(err|error)\s*(is not None|!=\s*None|:)")
NAKED_TUPLE_RETURN = re.compile(r"return\s+\w+\s*,\s*(True|False|None)\s*$")


def _go_in_python(files: list[FileDiff]) -> list[IdiomFinding]:
    findings = []
    err_pattern_count = 0

    for f in files:
        if f.language != "python":
            continue
        for line in f.added:
            if ERR_RETURN.search(line) or ERR_CHECK.search(line):
                err_pattern_count += 1

    if err_pattern_count >= 3:
        findings.append(IdiomFinding(
            signal="error_return_pattern",
            source_lang="go",
            detail=f"{err_pattern_count} Go-style error return patterns — use exceptions",
            severity=min(err_pattern_count / 5, 1.0),
        ))

    return findings


# --- C++/C patterns in Python ---

MANUAL_CLEANUP = re.compile(r"(\.close\(\)|\.release\(\)|\.dispose\(\)|\.shutdown\(\))\s*$")
NULL_PATTERN = re.compile(r"if\s+\w+\s*(==|!=)\s*None\s*:")  # C-style null checks vs `is None`


def _cpp_in_python(files: list[FileDiff]) -> list[IdiomFinding]:
    findings = []
    equality_none = 0

    for f in files:
        if f.language != "python":
            continue
        for line in f.added:
            if NULL_PATTERN.search(line):
                equality_none += 1

    if equality_none >= 3:
        findings.append(IdiomFinding(
            signal="equality_none",
            source_lang="c/cpp",
            detail=f"{equality_none} uses of '== None' or '!= None' — use 'is None' / 'is not None'",
            severity=min(equality_none / 5, 1.0),
        ))

    return findings


# --- JS patterns in Python ---

CALLBACK_PARAM = re.compile(r"def\s+\w+\(.*callback\s*[=:,)]")
PROMISE_LIKE = re.compile(r"\.(then|catch|finally)\s*\(")
UNDEFINED_CHECK = re.compile(r"if\s+\w+\s+is\s+None\s+or\s+\w+\s*==\s*['\"]")


def _js_in_python(files: list[FileDiff]) -> list[IdiomFinding]:
    findings = []
    callback_count = 0

    for f in files:
        if f.language != "python":
            continue
        for line in f.added:
            if CALLBACK_PARAM.search(line):
                callback_count += 1

    if callback_count >= 2:
        findings.append(IdiomFinding(
            signal="callback_pattern",
            source_lang="javascript",
            detail=f"{callback_count} functions with callback parameters — not Pythonic",
            severity=min(callback_count / 3, 1.0),
        ))

    return findings


def analyze_idioms(diff: Diff) -> IdiomReport:
    all_findings: list[IdiomFinding] = []

    all_findings.extend(_java_in_python(diff.files))
    all_findings.extend(_go_in_python(diff.files))
    all_findings.extend(_cpp_in_python(diff.files))
    all_findings.extend(_js_in_python(diff.files))

    if not all_findings:
        return IdiomReport(idiom_score=0)

    avg_severity = sum(f.severity for f in all_findings) / len(all_findings)
    score = avg_severity * 100

    return IdiomReport(idiom_score=min(score, 100), findings=all_findings)
