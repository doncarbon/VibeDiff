"""Tests for config loading."""

from vibediff.config import Config, load_config


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        cfg = load_config(str(tmp_path))
        assert cfg.ignore == []
        assert cfg.exclude == []
        assert cfg.grade_weights == {}
        assert cfg.thresholds == {}

    def test_loads_vibediff_toml(self, tmp_path):
        (tmp_path / ".vibediff.toml").write_text(
            'ignore = ["comment_density", "getter_setter"]\n'
            'exclude = ["vendor/*", "*.generated.py"]\n'
            "\n"
            "[thresholds]\n"
            "comment_ratio = 0.3\n"
        )
        cfg = load_config(str(tmp_path))
        assert cfg.ignore == ["comment_density", "getter_setter"]
        assert cfg.exclude == ["vendor/*", "*.generated.py"]
        assert cfg.thresholds == {"comment_ratio": 0.3}

    def test_loads_alt_filename(self, tmp_path):
        (tmp_path / "vibediff.toml").write_text(
            'ignore = ["broad_exceptions"]\n'
        )
        cfg = load_config(str(tmp_path))
        assert cfg.ignore == ["broad_exceptions"]

    def test_prefers_dotfile(self, tmp_path):
        (tmp_path / ".vibediff.toml").write_text('ignore = ["a"]\n')
        (tmp_path / "vibediff.toml").write_text('ignore = ["b"]\n')
        cfg = load_config(str(tmp_path))
        assert cfg.ignore == ["a"]

    def test_handles_invalid_toml(self, tmp_path):
        (tmp_path / ".vibediff.toml").write_text("not valid { toml")
        cfg = load_config(str(tmp_path))
        assert cfg.ignore == []

    def test_grade_weights(self, tmp_path):
        (tmp_path / ".vibediff.toml").write_text(
            "[grade_weights]\n"
            "ai = 0.4\n"
            "drift = 0.2\n"
            "collab = 0.2\n"
            "idiom = 0.2\n"
        )
        cfg = load_config(str(tmp_path))
        assert cfg.grade_weights["ai"] == 0.4
