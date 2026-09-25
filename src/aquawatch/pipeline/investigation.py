"""Rank active anomaly zones for sampling. The score is a product, not a model."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from aquawatch.geo.clip import geometry_point, load_features
from aquawatch.pipeline.anomaly import normalized_severity
from aquawatch.pipeline.priority import (
    consecutive_anomalous_dates,
    investigation_formula,
    nearest_distance,
    priority_score,
    proximity_factor,
)
from aquawatch.pipeline.series_alerts import SeriesAlert, parse_alert_id, severity_from_sigma


@dataclass
class RankedZone:
    rank: int
    zone_id: str
    date: str
    severity: float
    severity_label: str
    max_abs_sigma: float | None
    persistence: int
    proximity: float
    distance_to_intake_m: float | None
    distance_to_settlement_m: float | None
    priority: float
    sample_lat: float | None
    sample_lon: float | None
    indicators: list[str]
    confidence: float
    confidence_reasons: list[str]


def context_points(path: Path | None, water_body_id: str) -> list[tuple[float, float]]:
    if path is None:
        return []
    points = []
    for feature in load_features(path):
        props = feature.get("properties") or {}
        owner = props.get("water_body_id")
        if owner and owner != water_body_id:
            continue
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        point = geometry_point(geometry)
        if point is not None:
            points.append(point)
    return points


def rank_active_zones(
    alerts: list[SeriesAlert],
    observed_dates: dict[str, list[str]],
    *,
    intakes: list[tuple[float, float]],
    settlements: list[tuple[float, float]],
    intake_weight: float,
    settlement_weight: float,
    scale_m: float,
    z_cap: float,
    sigma_threshold: float,
) -> tuple[list[RankedZone], str]:
    """Keep zones whose latest stored date is anomalous and rank them.

    Persistence is the number of consecutive stored dates ending on that latest date.
    The sampling point is the zone centroid.
    """
    formula = investigation_formula(intake_weight, settlement_weight, scale_m, z_cap)
    by_zone: dict[str, list[SeriesAlert]] = defaultdict(list)
    for alert in alerts:
        by_zone[alert.zone_id].append(alert)

    ranked: list[RankedZone] = []
    for zone_id, zone_alerts in by_zone.items():
        anomalous = set()
        by_date: dict[str, SeriesAlert] = {}
        for alert in zone_alerts:
            parsed = parse_alert_id(alert.id)
            if parsed is None:
                continue
            date = parsed[2]
            anomalous.add(date)
            by_date[date] = alert
        timeline = observed_dates.get(zone_id) or sorted(anomalous)
        if not timeline:
            continue
        latest = timeline[-1]
        streak = consecutive_anomalous_dates(timeline, anomalous)
        if streak < 1 or latest not in anomalous:
            continue
        current = by_date[latest]
        max_abs = _max_abs_sigma(current)
        severity = normalized_severity(max_abs, z_cap)
        label = severity_from_sigma(max_abs, sigma_threshold)
        origin = None if current.lon is None or current.lat is None else (current.lon, current.lat)
        intake_distance = None if origin is None else nearest_distance(origin, intakes)
        settlement_distance = None if origin is None else nearest_distance(origin, settlements)
        proximity = proximity_factor(
            intake_distance,
            settlement_distance,
            intake_weight,
            settlement_weight,
            scale_m,
        )
        ranked.append(
            RankedZone(
                rank=0,
                zone_id=zone_id,
                date=latest,
                severity=severity,
                severity_label=label,
                max_abs_sigma=None if not math.isfinite(max_abs) else float(max_abs),
                persistence=streak,
                proximity=proximity,
                distance_to_intake_m=intake_distance,
                distance_to_settlement_m=settlement_distance,
                priority=priority_score(severity, streak, proximity),
                sample_lat=current.lat,
                sample_lon=current.lon,
                indicators=list(current.indicators),
                confidence=current.confidence,
                confidence_reasons=list(current.confidence_reasons),
            )
        )
    ranked.sort(key=lambda zone: (-zone.priority, zone.zone_id))
    for index, zone in enumerate(ranked, start=1):
        zone.rank = index
    return ranked, formula


def _max_abs_sigma(alert: SeriesAlert) -> float:
    if any(item.crossed and item.sigma is None and item.baseline_std == 0 for item in alert.evidence):
        return math.inf
    values = [abs(item.sigma) for item in alert.evidence if item.crossed and item.sigma is not None]
    return max(values) if values else 0.0
