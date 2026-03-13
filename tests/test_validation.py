"""Real-world validation tests — assert analyzers produce sane scores on corpus diffs."""

from pathlib import Path

import pytest

from vibediff.analyze import analyze_ai
from vibediff.collaboration import analyze_collaboration
from vibediff.diff import parse_diff
from vibediff.idiom import analyze_idioms

CORPUS = Path(__file__).parent / "fixtures" / "diffs" / "corpus"


def _load(name):
    return parse_diff((CORPUS / f"{name}.diff").read_text())


# --- AI detection ---

@pytest.mark.parametrize("name,min_score,max_score", [
    ("copilot_fastapi_crud", 60, 100),
    ("ai_java_patterns", 60, 100),
    ("ai_go_patterns", 40, 100),
    ("ai_test_generation", 40, 100),
    ("human_cache_fix", 0, 15),
    ("human_refactor", 0, 15),
])
def test_ai_detection_scores(name, min_score, max_score):
    report = analyze_ai(_load(name))
    assert min_score <= report.ai_score <= max_score, (
        f"{name}: expected AI score {min_score}-{max_score}, got {report.ai_score:.1f}"
    )


@pytest.mark.parametrize("name,expected_label", [
    ("copilot_fastapi_crud", "high"),
    ("ai_java_patterns", "high"),
    ("ai_go_patterns", "medium"),
    ("ai_test_generation", "medium"),
    ("human_cache_fix", "low"),
    ("human_refactor", "low"),
])
def test_ai_detection_labels(name, expected_label):
    report = analyze_ai(_load(name))
    assert report.label == expected_label, (
        f"{name}: expected '{expected_label}', got '{report.label}' (score={report.ai_score:.1f})"
    )


# --- Idiom contamination ---

@pytest.mark.parametrize("name,expected_signals", [
    ("ai_go_patterns", ["error_return_pattern"]),
    ("ai_java_patterns", ["getter_setter", "interface_naming"]),
    ("copilot_fastapi_crud", []),
    ("human_cache_fix", []),
])
def test_idiom_detection(name, expected_signals):
    report = analyze_idioms(_load(name))
    found = [f.signal for f in report.findings]
    for sig in expected_signals:
        assert sig in found, f"{name}: expected idiom '{sig}' not found in {found}"
    if not expected_signals:
        assert report.idiom_score < 10


# --- Collaboration ---

@pytest.mark.parametrize("name,min_score", [
    ("human_cache_fix", 80),
    ("human_refactor", 80),
    ("copilot_fastapi_crud", 80),
])
def test_collaboration_high_quality(name, min_score):
    report = analyze_collaboration(_load(name))
    assert report.collab_score >= min_score


def test_ai_tests_flag_generic_names():
    report = analyze_collaboration(_load("ai_test_generation"))
    signals = [f.signal for f in report.findings]
    assert "generic_names" in signals
