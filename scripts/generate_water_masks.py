"""Run segmentation over the cached archive and write mask files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aquawatch.api.deps import build_state  # noqa: E402
from aquawatch.geo.catalog import list_dates  # noqa: E402
from aquawatch.settings import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings(ROOT)
    state = build_state(settings)
    for body in settings.water_bodies:
        for date in list_dates(settings.scenes_dir, body.id, body.dates):
            analysis = state.runner.analyze(body.id, date)
            print(f"{body.id} {date} {analysis.status} {analysis.reason or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
