from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILES = [".vibediff.toml", "vibediff.toml"]


@dataclass
class Config:
    # signals to ignore (e.g. ["comment_density", "getter_setter"])
    ignore: list[str] = field(default_factory=list)

    # files to exclude from analysis (glob patterns)
    exclude: list[str] = field(default_factory=list)

    # grade weights (must sum to ~1.0 when drift is available)
    grade_weights: dict[str, float] = field(default_factory=dict)

    # per-signal threshold overrides
    thresholds: dict[str, float] = field(default_factory=dict)


def load_config(root: str = ".") -> Config:
    """Load config from .vibediff.toml if it exists."""
    for name in CONFIG_FILES:
        path = Path(root) / name
        if path.exists():
            return _parse(path)
    return Config()


def _parse(path: Path) -> Config:
    try:
        data = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return Config()

    cfg = Config()

    if "ignore" in data:
        cfg.ignore = list(data["ignore"])

    if "exclude" in data:
        cfg.exclude = list(data["exclude"])

    if "grade_weights" in data and isinstance(data["grade_weights"], dict):
        cfg.grade_weights = {
            k: float(v) for k, v in data["grade_weights"].items()
        }

    if "thresholds" in data and isinstance(data["thresholds"], dict):
        cfg.thresholds = {
            k: float(v) for k, v in data["thresholds"].items()
        }

    return cfg
