from vibediff.collaboration import CollabReport, analyze_collaboration
from vibediff.diff import Diff, FileDiff, Hunk


def _make_diff(lines: list[str], lang: str = "python") -> Diff:
    return Diff(files=[FileDiff(
        path=f"test.{lang[:2]}",
        language=lang,
        hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
    )])


class TestTodos:
    def test_many_todos_flagged(self):
        lines = [
            "x = 1  # TODO fix this\n",
            "y = 2  # TODO refactor\n",
            "z = 3  # TODO cleanup\n",
        ]
        report = analyze_collaboration(_make_diff(lines))
        assert any(f.signal == "unresolved_todos" for f in report.findings)

    def test_single_todo_ok(self):
        lines = ["x = 1  # TODO fix later\n", "y = 2\n"]
        report = analyze_collaboration(_make_diff(lines))
        assert not any(f.signal == "unresolved_todos" for f in report.findings)


class TestGenericNames:
    def test_too_many_generic_names(self):
        lines = [
            "data = get_stuff()\n",
            "result = process(data)\n",
            "output = format(result)\n",
            "value = convert(output)\n",
            "item = next(value)\n",
            "info = lookup(item)\n",
        ]
        report = analyze_collaboration(_make_diff(lines))
        assert any(f.signal == "generic_names" for f in report.findings)

    def test_specific_names_ok(self):
        lines = [
            "user_id = get_id()\n",
            "account = lookup(user_id)\n",
            "balance = account.balance\n",
            "total = sum(amounts)\n",
            "rate = balance / total\n",
        ]
        report = analyze_collaboration(_make_diff(lines))
        assert not any(f.signal == "generic_names" for f in report.findings)


class TestGenericTests:
    def test_generic_test_names_flagged(self):
        lines = [
            "def test_function_1():\n",
            "    pass\n",
            "def test_method_2():\n",
            "    pass\n",
        ]
        report = analyze_collaboration(_make_diff(lines))
        assert any(f.signal == "generic_tests" for f in report.findings)


class TestPlaceholders:
    def test_many_stubs_flagged(self):
        lines = [
            "def foo(): pass\n",
            "def bar(): ...\n",
            "def baz(): raise NotImplementedError\n",
        ]
        report = analyze_collaboration(_make_diff(lines))
        assert any(f.signal == "placeholders" for f in report.findings)


class TestUniformity:
    def test_uniform_comment_density_flagged(self):
        files = []
        for i in range(4):
            lines = [f"# comment {j}\n" if j % 5 == 0 else f"x_{j} = {j}\n" for j in range(20)]
            files.append(FileDiff(
                path=f"file_{i}.py",
                language="python",
                hunks=[Hunk(1, 1, 1, len(lines), added=lines)],
            ))
        report = analyze_collaboration(Diff(files=files))
        assert any(f.signal == "uniform_style" for f in report.findings)


class TestAnalyzeCollaboration:
    def test_clean_diff(self):
        lines = ["user_id = get_id()\n", "account = lookup(user_id)\n"]
        report = analyze_collaboration(_make_diff(lines))
        assert report.collab_score == 100

    def test_label(self):
        assert CollabReport(collab_score=80).label == "good"
        assert CollabReport(collab_score=50).label == "mixed"
        assert CollabReport(collab_score=20).label == "poor"

    def test_empty_diff(self):
        report = analyze_collaboration(Diff())
        assert report.collab_score == 100
