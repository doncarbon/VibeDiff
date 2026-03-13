from vibediff.diff import Diff, FileDiff, Hunk
from vibediff.drift import DriftReport, analyze_drift
from vibediff.fingerprint import Fingerprint


def _make_diff(lines: list[str], lang: str = "python") -> Diff:
    return Diff(files=[FileDiff(
        path=f"test.{lang[:2]}",
        language=lang,
        hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
    )])


def _snake_codebase() -> Fingerprint:
    return Fingerprint(
        files_scanned=20,
        total_lines=5000,
        snake_case_ratio=0.95,
        camel_case_ratio=0.02,
        avg_func_name_words=2.1,
        comment_ratio=0.08,
        avg_func_length=15,
        from_import_ratio=0.85,
        docstring_ratio=0.3,
    )


class TestNamingDrift:
    def test_camel_in_snake_codebase(self):
        diff = _make_diff([
            "def getUserById():\n",
            "    pass\n",
            "def saveUserData():\n",
            "    pass\n",
            "def deleteRecord():\n",
            "    pass\n",
        ])
        report = analyze_drift(diff, _snake_codebase())
        assert any(f.signal == "naming_convention" for f in report.findings)

    def test_matching_style_no_drift(self):
        diff = _make_diff([
            "def get_user():\n",
            "    pass\n",
            "def save_data():\n",
            "    pass\n",
        ])
        report = analyze_drift(diff, _snake_codebase())
        assert not any(f.signal == "naming_convention" for f in report.findings)


class TestCommentDrift:
    def test_over_commented(self):
        fp = _snake_codebase()
        fp.comment_ratio = 0.05
        lines = [f"# comment {i}\n" if i % 2 == 0 else f"x_{i} = {i}\n" for i in range(20)]
        diff = _make_diff(lines)
        report = analyze_drift(diff, fp)
        assert any(f.signal == "comment_density" for f in report.findings)


class TestFuncLengthDrift:
    def test_much_longer_functions(self):
        fp = _snake_codebase()
        fp.avg_func_length = 10
        lines = ["def long_func():\n"] + [f"    x_{i} = {i}\n" for i in range(40)]
        lines += ["def another_long():\n"] + [f"    y_{i} = {i}\n" for i in range(35)]
        diff = _make_diff(lines)
        report = analyze_drift(diff, fp)
        assert any(f.signal == "function_length" for f in report.findings)


class TestImportDrift:
    def test_bare_imports_in_from_codebase(self):
        fp = _snake_codebase()
        fp.from_import_ratio = 0.9
        diff = _make_diff([
            "import os\n",
            "import sys\n",
            "import json\n",
            "import re\n",
        ])
        report = analyze_drift(diff, fp)
        assert any(f.signal == "import_style" for f in report.findings)


class TestAnalyzeDrift:
    def test_empty_diff(self):
        report = analyze_drift(Diff(), _snake_codebase())
        assert report.drift_score == 0

    def test_label(self):
        assert DriftReport(drift_score=70).label == "high"
        assert DriftReport(drift_score=40).label == "medium"
        assert DriftReport(drift_score=10).label == "low"
