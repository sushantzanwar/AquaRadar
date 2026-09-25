"""Validate the cache, fit baselines when scenes exist, and print the demo path."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aquawatch.api.deps import build_state  # noqa: E402
from aquawatch.geo.catalog import list_dates, scene_dir  # noqa: E402
from aquawatch.llm.retriever import Retriever  # noqa: E402
from aquawatch.pipeline.temporal import fit_rows  # noqa: E402
from aquawatch.settings import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings(ROOT)
    state = build_state(settings)
    print("AquaWatch seed")
    print(settings.disclaimer)
    any_scene = False
    for body in settings.water_bodies:
        for date in list_dates(settings.scenes_dir, body.id, body.dates):
            folder = scene_dir(settings.scenes_dir, body.id, date)
            mark = "on disk" if folder.is_dir() else "missing"
            print(f"  {body.id} {date} {mark}")
            any_scene = any_scene or folder.is_dir()
    if any_scene and state.runner.baselines.count() == 0:
        rows = fit_rows(state.runner.observations())
        state.runner.baselines.replace_all(rows)
        state.runner.clear_cache()
        print(f"fit {len(rows)} baseline rows")
    elif not any_scene:
        print("No scene folders yet. Drop GeoTIFFs under data/scenes/{water_body_id}/{YYYYMMDD}/.")
    passages = Retriever(settings.corpus_dir, settings.cache_dir).build_index()
    print(f"corpus passages: {passages}")
    print("Walkthrough: open a water body, swipe two dates, open a flagged zone,")
    print("read the evidence card, ask the assistant, inject a plume, submit a photo.")
    print("API http://127.0.0.1:8000/docs  UI http://127.0.0.1:5173")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
