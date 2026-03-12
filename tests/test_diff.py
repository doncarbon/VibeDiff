from vibediff.diff import Diff, FileDiff, Hunk, detect_language, parse_diff


class TestDetectLanguage:
    def test_common_extensions(self):
        assert detect_language("main.py") == "python"
        assert detect_language("app.js") == "javascript"
        assert detect_language("lib.ts") == "typescript"
        assert detect_language("App.tsx") == "typescript"
        assert detect_language("main.go") == "go"
        assert detect_language("Main.java") == "java"

    def test_unknown(self):
        assert detect_language("Makefile") == "unknown"

    def test_case_insensitive(self):
        assert detect_language("FOO.PY") == "python"


class TestHunk:
    def test_fields(self):
        h = Hunk(1, 10, 1, 15, added=["a\n", "b\n"], removed=["x\n"])
        assert len(h.added) == 2
        assert len(h.removed) == 1


class TestFileDiff:
    def test_lines_across_hunks(self):
        f = FileDiff(
            path="test.py",
            language="python",
            hunks=[
                Hunk(1, 5, 1, 7, added=["a\n", "b\n"]),
                Hunk(10, 3, 12, 5, added=["c\n"], removed=["x\n"]),
            ],
        )
        assert f.added == ["a\n", "b\n", "c\n"]
        assert f.removed == ["x\n"]


class TestDiff:
    def test_languages(self):
        d = Diff(files=[
            FileDiff(path="a.py", language="python"),
            FileDiff(path="b.js", language="javascript"),
        ])
        assert d.languages == {"python", "javascript"}

    def test_empty(self):
        d = Diff()
        assert d.languages == set()


class TestParseDiff:
    def test_empty(self):
        assert len(parse_diff("").files) == 0

    def test_ai_generated(self, ai_generated_diff):
        d = parse_diff(ai_generated_diff)
        assert len(d.files) == 1
        f = d.files[0]
        assert f.language == "python"
        assert f.is_new is True
        assert len(f.added) == 58

    def test_human_written(self, human_written_diff):
        d = parse_diff(human_written_diff)
        assert len(d.files) == 1
        f = d.files[0]
        assert f.path == "cache.py"
        assert len(f.added) > 0
        assert len(f.removed) > 0

    def test_mixed(self, mixed_collaboration_diff):
        d = parse_diff(mixed_collaboration_diff)
        assert len(d.files) == 1
        assert d.files[0].path == "routes.py"
