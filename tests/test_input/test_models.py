"""Tests for input data models."""

from vibediff.input.models import DiffFile, DiffHunk, PatchContext, detect_language


class TestDetectLanguage:
    def test_python(self):
        assert detect_language("src/main.py") == "python"

    def test_javascript(self):
        assert detect_language("app/index.js") == "javascript"

    def test_typescript(self):
        assert detect_language("src/utils.ts") == "typescript"

    def test_tsx(self):
        assert detect_language("components/App.tsx") == "typescript"

    def test_go(self):
        assert detect_language("cmd/server.go") == "go"

    def test_java(self):
        assert detect_language("Main.java") == "java"

    def test_unknown(self):
        assert detect_language("Makefile") == "unknown"

    def test_case_insensitive(self):
        assert detect_language("README.PY") == "python"


class TestDiffHunk:
    def test_creation(self):
        hunk = DiffHunk(
            source_start=1,
            source_length=10,
            target_start=1,
            target_length=15,
            added_lines=["line1\n", "line2\n"],
            removed_lines=["old\n"],
        )
        assert len(hunk.added_lines) == 2
        assert len(hunk.removed_lines) == 1


class TestDiffFile:
    def test_added_lines_across_hunks(self):
        f = DiffFile(
            path="test.py",
            language="python",
            hunks=[
                DiffHunk(1, 5, 1, 7, added_lines=["a\n", "b\n"], removed_lines=[]),
                DiffHunk(10, 3, 12, 5, added_lines=["c\n"], removed_lines=["x\n"]),
            ],
        )
        assert f.added_lines == ["a\n", "b\n", "c\n"]
        assert f.removed_lines == ["x\n"]
        assert f.total_added == 3
        assert f.total_removed == 1

    def test_new_file(self):
        f = DiffFile(path="new.py", language="python", is_new=True)
        assert f.is_new is True
        assert f.total_added == 0


class TestPatchContext:
    def test_totals(self):
        patch = PatchContext(
            files=[
                DiffFile(
                    path="a.py",
                    language="python",
                    hunks=[DiffHunk(1, 1, 1, 3, added_lines=["x\n", "y\n"], removed_lines=[])],
                ),
                DiffFile(
                    path="b.js",
                    language="javascript",
                    hunks=[DiffHunk(1, 2, 1, 1, added_lines=[], removed_lines=["z\n"])],
                ),
            ]
        )
        assert patch.total_added == 2
        assert patch.total_removed == 1
        assert patch.languages == {"python", "javascript"}

    def test_empty_patch(self):
        patch = PatchContext()
        assert patch.total_added == 0
        assert patch.total_removed == 0
        assert patch.languages == set()
