from vibediff.diff import Diff, FileDiff, Hunk
from vibediff.idiom import IdiomReport, analyze_idioms


def _make_diff(lines: list[str], lang: str = "python") -> Diff:
    return Diff(files=[FileDiff(
        path=f"test.{lang[:2]}",
        language=lang,
        hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
    )])


class TestJavaInPython:
    def test_getter_setter_flagged(self):
        lines = [
            "def getName(self):\n",
            "    return self._name\n",
            "def setName(self, name):\n",
            "    self._name = name\n",
            "def getValue(self):\n",
            "    return self._value\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert any(f.signal == "getter_setter" for f in report.findings)

    def test_property_style_ok(self):
        lines = [
            "@property\n",
            "def name(self):\n",
            "    return self._name\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert not any(f.signal == "getter_setter" for f in report.findings)

    def test_interface_naming_flagged(self):
        lines = [
            "class UserInterface(ABC):\n",
            "    pass\n",
            "class AbstractHandler(ABC):\n",
            "    pass\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert any(f.signal == "interface_naming" for f in report.findings)


class TestGoInPython:
    def test_error_return_pattern_flagged(self):
        lines = [
            "return user, None\n",
            "return None, err\n",
            "return data, error\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert any(f.signal == "error_return_pattern" for f in report.findings)

    def test_exception_style_ok(self):
        lines = [
            "raise ValueError('bad input')\n",
            "return user\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert not any(f.signal == "error_return_pattern" for f in report.findings)


class TestCppInPython:
    def test_equality_none_flagged(self):
        lines = [
            "if user == None:\n",
            "    pass\n",
            "if data != None:\n",
            "    pass\n",
            "if result == None:\n",
            "    pass\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert any(f.signal == "equality_none" for f in report.findings)

    def test_is_none_ok(self):
        lines = [
            "if user is None:\n",
            "    pass\n",
            "if data is not None:\n",
            "    pass\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert not any(f.signal == "equality_none" for f in report.findings)


class TestJsInPython:
    def test_callback_pattern_flagged(self):
        lines = [
            "def fetch_data(url, callback=None):\n",
            "    pass\n",
            "def process(items, callback):\n",
            "    pass\n",
        ]
        report = analyze_idioms(_make_diff(lines))
        assert any(f.signal == "callback_pattern" for f in report.findings)


class TestAnalyzeIdioms:
    def test_clean_diff(self):
        lines = ["user = get_user()\n", "name = user.name\n"]
        report = analyze_idioms(_make_diff(lines))
        assert report.idiom_score == 0
        assert not report.findings

    def test_label(self):
        assert IdiomReport(idiom_score=70).label == "high"
        assert IdiomReport(idiom_score=30).label == "medium"
        assert IdiomReport(idiom_score=10).label == "low"

    def test_non_python_ignored(self):
        lines = [
            "def getName(self):\n",
            "def setName(self, name):\n",
        ]
        report = analyze_idioms(_make_diff(lines, lang="javascript"))
        assert not report.findings

    def test_empty_diff(self):
        report = analyze_idioms(Diff())
        assert report.idiom_score == 0
