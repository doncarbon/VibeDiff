from vibediff.analyze import (
    Finding,
    AnalysisReport,
    analyze_ai,
    _score_comments,
    _score_naming,
    _score_burstiness,
    _score_structure,
    _word_count,
)
from vibediff.diff import FileDiff, Hunk, Diff, parse_diff


class TestWordCount:
    def test_snake_case(self):
        assert _word_count("get_user") == 2
        assert _word_count("authenticate_user_credentials") == 3

    def test_camel_case(self):
        assert _word_count("getUser") == 2
        assert _word_count("authenticateUserCredentials") == 3

    def test_single(self):
        assert _word_count("user") == 1
        assert _word_count("x") == 1


class TestCommentScoring:
    def _make_files(self, lines: list[str]) -> list[FileDiff]:
        return [FileDiff(
            path="test.py", language="python",
            hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
        )]

    def test_low_comments(self):
        lines = ["x = 1\n", "y = 2\n", "z = x + y\n"] * 5
        score, findings = _score_comments(self._make_files(lines))
        assert score == 0
        assert findings == []

    def test_high_comment_density(self):
        lines = ["# Initialize the variable\n", "x = 1\n"] * 10
        score, findings = _score_comments(self._make_files(lines))
        assert score > 0
        assert any(f.signal == "comment_density" for f in findings)

    def test_restating_comments(self):
        lines = [
            "# Initialize the database connection\n",
            "db = connect()\n",
            "# Check if the user exists\n",
            "user = find()\n",
            "# Return the result\n",
            "return user\n",
            "# Validate that the input is correct\n",
            "check(input)\n",
        ]
        score, findings = _score_comments(self._make_files(lines))
        assert any(f.signal == "restating_comments" for f in findings)

    def test_section_headers(self):
        lines = [
            "# --- Helper Functions ---\n",
            "def foo(): pass\n",
            "# === Main Logic ===\n",
            "def bar(): pass\n",
            "x = 1\n",
        ]
        score, findings = _score_comments(self._make_files(lines))
        assert any(f.signal == "section_headers" for f in findings)


class TestNamingScoring:
    def _make_files(self, lines: list[str]) -> list[FileDiff]:
        return [FileDiff(
            path="test.py", language="python",
            hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
        )]

    def test_verbose_names(self):
        lines = [
            "def authenticate_user_credentials_with_token(): pass\n",
            "def validate_input_parameters_and_sanitize(): pass\n",
            "def initialize_database_connection_pool(): pass\n",
        ]
        score, findings = _score_naming(self._make_files(lines))
        assert any(f.signal == "verbose_names" for f in findings)

    def test_normal_names(self):
        lines = [
            "def login(): pass\n",
            "def get_user(): pass\n",
            "def save(): pass\n",
        ]
        score, findings = _score_naming(self._make_files(lines))
        assert not any(f.signal == "verbose_names" for f in findings)


class TestBurstiness:
    def _make_files(self, lines: list[str]) -> list[FileDiff]:
        return [FileDiff(
            path="test.py", language="python",
            hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
        )]

    def test_uniform_lines(self):
        # Simulate AI-like uniform complexity
        lines = [f"    result_{i} = func_{i}(arg_{i})\n" for i in range(30)]
        score, findings = _score_burstiness(self._make_files(lines))
        assert any(f.signal == "low_burstiness" for f in findings)

    def test_varied_lines(self):
        # Simulate human-like varied complexity
        lines = [
            "x = 1\n",
            "if x > 0 and some_condition(x, y, z) or other_func(a, b, c, d=[1,2,3]):\n",
            "    pass\n",
            "y = 2\n",
            "result = very_complex_call(nested(deep(x)), config={'a': 1, 'b': [2,3]}, flag=True)\n",
        ] * 4
        score, findings = _score_burstiness(self._make_files(lines))
        # Should have higher variance, less likely to flag
        low_burst = [f for f in findings if f.signal == "low_burstiness"]
        if low_burst:
            assert low_burst[0].severity < 0.5


class TestStructure:
    def _make_files(self, lines: list[str]) -> list[FileDiff]:
        return [FileDiff(
            path="test.py", language="python",
            hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
        )]

    def test_excessive_guards(self):
        lines = [
            "def foo(x):\n",
            "    if x is None:\n",
            "        return\n",
            "def bar(y):\n",
            "    if y is None:\n",
            "        return\n",
            "def baz(z):\n",
            "    if z is None:\n",
            "        return\n",
        ]
        score, findings = _score_structure(self._make_files(lines))
        assert any(f.signal == "excessive_guards" for f in findings)

    def test_broad_exceptions(self):
        lines = [
            "def foo():\n",
            "    try:\n",
            "        do_thing()\n",
            "    except Exception as e:\n",
            "        log(e)\n",
            "def bar():\n",
            "    try:\n",
            "        do_other()\n",
            "    except Exception as e:\n",
            "        log(e)\n",
        ]
        score, findings = _score_structure(self._make_files(lines))
        assert any(f.signal == "broad_exceptions" for f in findings)


class TestAnalyzeAI:
    def test_ai_generated_fixture(self, ai_generated_diff):
        d = parse_diff(ai_generated_diff)
        report = analyze_ai(d)
        assert isinstance(report, AnalysisReport)
        assert report.ai_score > 0
        assert len(report.findings) > 0

    def test_human_fixture(self, human_written_diff):
        d = parse_diff(human_written_diff)
        report = analyze_ai(d)
        # Human code should score lower than AI
        assert report.ai_score < 50

    def test_empty_diff(self):
        d = Diff()
        report = analyze_ai(d)
        assert report.ai_score == 0
        assert report.findings == []

    def test_label(self):
        assert AnalysisReport(ai_score=80).label == "high"
        assert AnalysisReport(ai_score=50).label == "medium"
        assert AnalysisReport(ai_score=20).label == "low"
