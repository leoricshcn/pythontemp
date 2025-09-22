from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict

import pytest


FIXTURE_LABELS = (
    "Q3 2025",
    "Q2 2025",
)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def available_quarter_labels() -> tuple[str, ...]:
    return FIXTURE_LABELS


@pytest.fixture(scope="session")
def official_html_loader(fixtures_dir: Path) -> Callable[[str], str]:
    @lru_cache(maxsize=None)
    def _load(label: str) -> str:
        normalized = label.replace(" ", "_")
        path = fixtures_dir / f"{normalized}_official.html"
        if not path.exists():
            raise FileNotFoundError(f"Official HTML fixture not found for {label} at {path}")
        return path.read_text(encoding="utf-8")

    return _load


@pytest.fixture(scope="session")
def recommended_pdf_loader(fixtures_dir: Path) -> Callable[[str], bytes]:
    @lru_cache(maxsize=None)
    def _load(label: str) -> bytes:
        normalized = label.replace(" ", "_")
        path = fixtures_dir / f"{normalized}_recommended.pdf"
        if not path.exists():
            raise FileNotFoundError(f"Recommended PDF fixture not found for {label} at {path}")
        return path.read_bytes()

    return _load


@pytest.fixture(scope="session")
def sample_quarters(available_quarter_labels: tuple[str, ...]) -> tuple[str, ...]:
    return available_quarter_labels
