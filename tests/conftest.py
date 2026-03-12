"""Shared test fixtures for VibeDiff."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DIFFS_DIR = FIXTURES_DIR / "diffs"


@pytest.fixture
def ai_generated_diff() -> str:
    return (DIFFS_DIR / "ai_generated.diff").read_text()


@pytest.fixture
def human_written_diff() -> str:
    return (DIFFS_DIR / "human_written.diff").read_text()


@pytest.fixture
def mixed_collaboration_diff() -> str:
    return (DIFFS_DIR / "mixed_collaboration.diff").read_text()
