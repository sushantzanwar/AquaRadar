"""Season labels, baseline lookup, and fitting from per-date zone means."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass


def season_of(date: str) -> str:
    month = int(date[4:6])
    if month in (12, 1, 2):
        return "DJF"
    if month in (3, 4, 5):
        return "MAM"
    if month in (6, 7, 8):
        return "JJA"
    return "SON"


@dataclass
class BaselineView:
    mean: float
    std: float | None
    sample_count: int
    season: str
    used_fallback: bool


def select_baseline(season_row: dict | None, all_row: dict | None, season: str) -> BaselineView | None:
    chosen = season_row or all_row
    if chosen is None:
        return None
    return BaselineView(
        mean=float(chosen["mean"]),
        std=None if chosen["std"] is None else float(chosen["std"]),
        sample_count=int(chosen["sample_count"]),
        season=str(chosen["season"]),
        used_fallback=season_row is None and all_row is not None and season != "ALL",
    )


def persistence_ratio(flags: list[bool]) -> float:
    if not flags:
        return 0.0
    return sum(1 for flag in flags if flag) / len(flags)


def fit_rows(observations: list[dict]) -> list[dict]:
    """observations: water_body_id, zone_id, indicator, date, value."""
    grouped: dict[tuple, list[float]] = defaultdict(list)
    all_grouped: dict[tuple, list[float]] = defaultdict(list)
    for obs in observations:
        if obs.get("value") is None or not math.isfinite(obs["value"]):
            continue
        season = season_of(obs["date"])
        key = (obs["water_body_id"], obs["zone_id"], obs["indicator"], season)
        grouped[key].append(float(obs["value"]))
        all_key = (obs["water_body_id"], obs["zone_id"], obs["indicator"], "ALL")
        all_grouped[all_key].append(float(obs["value"]))

    rows = []
    for bucket in (grouped, all_grouped):
        for (body, zone, indicator, season), values in bucket.items():
            mean = sum(values) / len(values)
            if len(values) < 2:
                std = None
            else:
                var = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
                std = math.sqrt(var)
            rows.append(
                {
                    "water_body_id": body,
                    "zone_id": zone,
                    "indicator": indicator,
                    "season": season,
                    "mean": mean,
                    "std": std,
                    "sample_count": len(values),
                }
            )
    return rows
