"""Load the synthetic zone series used by the anomaly tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

@pytest.fixture
def series() -> dict:
    path = Path(__file__).parent / "fixtures" / "synthetic_zone_series.json"
    return json.loads(path.read_text(encoding="utf-8"))
