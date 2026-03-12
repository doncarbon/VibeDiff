"""Tests for git diff parsing."""

from vibediff.input.git_diff import parse_unified_diff


class TestParseUnifiedDiff:
    def test_empty_diff(self):
        patch = parse_unified_diff("")
        assert len(patch.files) == 0

    def test_ai_generated_diff(self, ai_generated_diff):
        patch = parse_unified_diff(ai_generated_diff)
        assert len(patch.files) == 1

        f = patch.files[0]
        assert f.path == "src/auth/user_authentication_handler.py"
        assert f.language == "python"
        assert f.is_new is True
        assert f.total_added == 58
        assert f.total_removed == 0

    def test_human_written_diff(self, human_written_diff):
        patch = parse_unified_diff(human_written_diff)
        assert len(patch.files) == 1

        f = patch.files[0]
        assert f.path == "cache.py"
        assert f.language == "python"
        assert f.is_new is False
        assert f.total_added > 0
        assert f.total_removed > 0

    def test_mixed_diff(self, mixed_collaboration_diff):
        patch = parse_unified_diff(mixed_collaboration_diff)
        assert len(patch.files) == 1

        f = patch.files[0]
        assert f.path == "routes.py"
        assert f.language == "python"

    def test_multiple_hunks_parsed(self, human_written_diff):
        patch = parse_unified_diff(human_written_diff)
        f = patch.files[0]
        assert len(f.hunks) >= 1
        for hunk in f.hunks:
            assert hunk.source_start > 0
            assert hunk.target_start > 0

    def test_languages_property(self, ai_generated_diff):
        patch = parse_unified_diff(ai_generated_diff)
        assert "python" in patch.languages
