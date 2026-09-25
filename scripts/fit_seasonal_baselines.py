"""Fit seasonal baselines from cached scenes into SQLite."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aquawatch.api.deps import build_state  # noqa: E402
from aquawatch.pipeline.temporal import fit_rows  # noqa: E402
from aquawatch.settings import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings(ROOT)
    state = build_state(settings)
    rows = fit_rows(state.runner.observations())
    state.runner.baselines.replace_all(rows)
    state.runner.clear_cache()
    print(f"wrote {len(rows)} baseline rows to {settings.baselines_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
