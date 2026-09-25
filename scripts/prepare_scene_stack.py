"""Check cached scene folders. Not imported by the API."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aquawatch.geo.catalog import band_paths, list_dates, scene_dir  # noqa: E402
from aquawatch.settings import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings(ROOT)
    failed = 0
    for body in settings.water_bodies:
        print(body.id)
        for date in list_dates(settings.scenes_dir, body.id, body.dates):
            folder = scene_dir(settings.scenes_dir, body.id, date)
            if not folder.is_dir():
                print(f"  {date}  missing")
                if date in body.dates:
                    failed += 1
                continue
            _paths, missing = band_paths(folder)
            if missing:
                print(f"  {date}  unusable  missing {','.join(missing)}")
                failed += 1
            else:
                print(f"  {date}  bands ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
