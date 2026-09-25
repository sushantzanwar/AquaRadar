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


@dataclass(frozen=True)
class AdaptivePoint:
    """One date on a zone/indicator series, with the baseline fit from the other dates."""

    date: str
    value: float
    baseline_mean: float | None
    baseline_std: float | None
    baseline_low: float | None
    baseline_high: float | None
    sample_count: int
    season: str
    used_fallback: bool
    raster_path: str | None = None


def adaptive_series(observations: list[dict], *, min_season_samples: int = 2) -> dict[str, dict[str, list[AdaptivePoint]]]:
    """Seasonal leave-one-out mean and ±1 standard-deviation band.

    ``observations`` are dicts with zone_id, indicator, date, value, and an
    optional raster_path. Same-season peers are used when at least
    ``min_season_samples`` other dates exist; otherwise the band falls back
    to every other date. The date being scored is not part of its own baseline.
    """
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for obs in observations:
        value = obs.get("value")
        if value is None or not math.isfinite(value):
            continue
        grouped[(str(obs["indicator"]), str(obs["zone_id"]))].append(obs)

    series: dict[str, dict[str, list[AdaptivePoint]]] = {}
    for (indicator, zone_id), rows in grouped.items():
        rows.sort(key=lambda item: item["date"])
        points = [_adaptive_point(rows, index, min_season_samples) for index in range(len(rows))]
        series.setdefault(indicator, {})[zone_id] = points
    return series


def series_confidence(points: list[AdaptivePoint], min_baseline_samples: int) -> tuple[float, list[str]]:
    """Thin history narrows confidence. A full sample can still note a seasonal fallback."""
    reasons = ["relative_index"]
    if not points:
        return 0.0, ["no_observations", *reasons]
    smallest = min(point.sample_count for point in points)
    if smallest < min_baseline_samples:
        confidence = 0.0 if min_baseline_samples <= 0 else smallest / float(min_baseline_samples)
        reasons.insert(0, "baseline_sample_size")
        if any(point.used_fallback for point in points):
            reasons.append("seasonal_fallback")
        return confidence, reasons
    if any(point.used_fallback for point in points):
        reasons.append("seasonal_fallback")
    return 1.0, reasons


def _adaptive_point(rows: list[dict], index: int, min_season_samples: int) -> AdaptivePoint:
    current = rows[index]
    season = season_of(str(current["date"]))
    others = [row for row_index, row in enumerate(rows) if row_index != index]
    seasonal = [row for row in others if season_of(str(row["date"])) == season]
    if len(seasonal) >= min_season_samples:
        chosen = seasonal
        used_fallback = False
    else:
        chosen = others
        used_fallback = True
    mean, std = _mean_std([float(row["value"]) for row in chosen]) if chosen else (None, None)
    low, high = _band(mean, std)
    return AdaptivePoint(
        date=str(current["date"]),
        value=float(current["value"]),
        baseline_mean=mean,
        baseline_std=std,
        baseline_low=low,
        baseline_high=high,
        sample_count=len(chosen),
        season=season,
        used_fallback=used_fallback,
        raster_path=None if current.get("raster_path") is None else str(current["raster_path"]),
    )


def _mean_std(values: list[float]) -> tuple[float, float | None]:
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, None
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance)


def _band(mean: float | None, std: float | None) -> tuple[float | None, float | None]:
    if mean is None:
        return None, None
    if std is None:
        return mean, mean
    return mean - std, mean + std


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
