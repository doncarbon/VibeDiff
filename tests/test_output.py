import json

from vibediff.analyze import AnalysisReport, Finding
from vibediff.cli import _compute_grade, _to_json, _to_markdown
from vibediff.collaboration import CollabFinding, CollabReport
from vibediff.drift import DriftFinding, DriftReport
from vibediff.idiom import IdiomFinding, IdiomReport


def _empty_reports():
    return (
        AnalysisReport(ai_score=0),
        None,
        CollabReport(collab_score=100),
        IdiomReport(idiom_score=0),
    )


def _full_reports():
    ai = AnalysisReport(ai_score=58, findings=[
        Finding(signal="restating_comments", detail="4 comments restate code", severity=0.6, locations=["foo.py"]),
    ])
    drift = DriftReport(drift_score=42, findings=[
        DriftFinding(signal="naming_convention", expected="snake_case", found="camelCase", severity=0.7),
    ])
    collab = CollabReport(collab_score=65, findings=[
        CollabFinding(signal="unresolved_todos", detail="3 TODO comments", severity=0.5),
    ])
    idiom = IdiomReport(idiom_score=40, findings=[
        IdiomFinding(signal="getter_setter", source_lang="java", detail="3 getter/setter methods", severity=0.6, locations=["getName"]),
    ])
    return ai, drift, collab, idiom


class TestGrade:
    def test_clean_code_gets_a(self):
        assert _compute_grade(0, 0, 100, 0) == "A"

    def test_all_bad_gets_f(self):
        assert _compute_grade(100, 100, 0, 100) == "F"

    def test_medium_scores_get_c_or_d(self):
        grade = _compute_grade(58, 42, 65, 40)
        assert grade in ("C", "D")

    def test_no_drift_still_grades(self):
        grade = _compute_grade(0, None, 100, 0)
        assert grade == "A"

    def test_grade_ordering(self):
        g1 = _compute_grade(10, None, 90, 5)
        g2 = _compute_grade(80, None, 30, 70)
        assert g1 < g2  # A < D alphabetically, better grades come first


class TestJsonOutput:
    def test_clean_reports(self):
        ai, drift, collab, idiom = _empty_reports()
        result = _to_json("A", ai, drift, collab, idiom, 1, 10, 5)
        assert result["grade"] == "A"
        assert result["files"] == 1
        assert result["lines_added"] == 10
        assert result["ai_detection"]["score"] == 0
        assert result["ai_detection"]["findings"] == []
        assert "style_drift" not in result

    def test_full_reports(self):
        ai, drift, collab, idiom = _full_reports()
        result = _to_json("D", ai, drift, collab, idiom, 3, 180, 12)
        assert result["grade"] == "D"
        assert result["ai_detection"]["score"] == 58
        assert len(result["ai_detection"]["findings"]) == 1
        assert result["style_drift"]["score"] == 42
        assert result["collaboration"]["score"] == 65
        assert result["idiom_contamination"]["score"] == 40

    def test_json_serializable(self):
        ai, drift, collab, idiom = _full_reports()
        result = _to_json("D", ai, drift, collab, idiom, 3, 180, 12)
        output = json.dumps(result)
        assert isinstance(json.loads(output), dict)


class TestMarkdownOutput:
    def test_clean_reports(self):
        ai, drift, collab, idiom = _empty_reports()
        md = _to_markdown("A", ai, drift, collab, idiom, 1, 10, 5)
        assert "Grade: A" in md
        assert "**Clean.**" in md

    def test_full_reports(self):
        ai, drift, collab, idiom = _full_reports()
        md = _to_markdown("D", ai, drift, collab, idiom, 3, 180, 12)
        assert "Grade: D" in md
        assert "### AI Detection" in md
        assert "### Style Drift" in md
        assert "### Collaboration" in md
        assert "### Idiom Contamination" in md
        assert "`restating_comments`" in md
        assert "`naming_convention`" in md
        assert "snake_case" in md
        assert "java" in md

    def test_no_drift_section_without_fingerprint(self):
        ai, _, collab, idiom = _full_reports()
        md = _to_markdown("C", ai, None, collab, idiom, 3, 180, 12)
        assert "### Style Drift" not in md
