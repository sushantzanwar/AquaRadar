"""Anomaly alerts computed from stored zone series. Nothing here is a fixed demo payload."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from aquawatch.pipeline.alerts import iso_date
from aquawatch.pipeline.anomaly import z_score
from aquawatch.pipeline.temporal import AdaptivePoint
from aquawatch.storage.zone_series import INDICATOR_ORDER, INDICATOR_UNITS

_ALERT_ID = re.compile(r"^sa-(.+)-(r\d+c\d+)-(\d{8})$")
_DISPLAY = {
    "extent": "extent",
    "turbidity": "turbidity",
    "chlorophyll": "chlorophyll-a",
    "transparency": "transparency",
}


@dataclass
class AlertEvidence:
    indicator: str
    value: float
    baseline_mean: float
    baseline_std: float | None
    baseline_low: float | None
    baseline_high: float | None
    sigma: float | None
    threshold: float
    crossed: bool
    sample_count: int
    unit: str


@dataclass
class SeriesAlert:
    id: str
    water_body_id: str
    water_body_name: str
    zone_id: str
    lat: float | None
    lon: float | None
    polygon: dict | None
    datetime: str
    affected_region: str
    indicators: list[str]
    compound: bool
    severity: str
    confidence: float
    confidence_reasons: list[str]
    template: str
    evidence: list[AlertEvidence] = field(default_factory=list)
    disclaimer: str = ""


def alert_id(water_body_id: str, zone_id: str, date: str) -> str:
    return f"sa-{water_body_id}-{zone_id}-{date}"


def parse_alert_id(value: str) -> tuple[str, str, str] | None:
    match = _ALERT_ID.fullmatch(value)
    if match is None:
        return None
    return match.group(1), match.group(2), match.group(3)


def severity_from_sigma(max_abs_sigma: float, threshold: float) -> str:
    """low just past the threshold, med one sigma higher, high two sigma higher."""
    if not math.isfinite(max_abs_sigma) or max_abs_sigma > threshold + 2:
        return "high"
    if max_abs_sigma > threshold + 1:
        return "med"
    return "low"


def detection_confidence(
    valid_fraction: float | None,
    disagreement_fraction: float | None,
    sample_count: int,
    min_baseline_samples: int,
) -> tuple[float, list[str]]:
    """Confidence is the weakest of clear-pixel fraction, mask agreement, and baseline length."""
    parts: list[float] = []
    reasons: list[str] = []
    if valid_fraction is None:
        reasons.append("valid_fraction_missing")
    else:
        clear = _clamp(valid_fraction)
        parts.append(clear)
        if clear < 1:
            reasons.append("valid_pixel_fraction")
    if disagreement_fraction is None:
        reasons.append("mask_agreement_missing")
    else:
        agreement = _clamp(1.0 - disagreement_fraction)
        parts.append(agreement)
        if agreement < 1:
            reasons.append("mask_agreement")
    if min_baseline_samples <= 0:
        history = 1.0
    else:
        history = _clamp(sample_count / float(min_baseline_samples))
    parts.append(history)
    if sample_count < min_baseline_samples:
        reasons.append("baseline_sample_size")
    reasons.append("relative_index")
    return (min(parts) if parts else 0.0), reasons


def build_series_alerts(
    water_body_id: str,
    water_body_name: str,
    series: dict[str, dict[str, list[AdaptivePoint]]],
    quality_by_date: dict[str, dict],
    *,
    sigma_threshold: float,
    min_baseline_samples: int,
    disclaimer: str,
    locations: dict[tuple[str, str], tuple[float, float, dict] | None] | None = None,
) -> list[SeriesAlert]:
    """Flag a zone-date when any indicator is more than ``sigma_threshold`` from its baseline.

    Two or more indicators in the same zone on the same date become one compound alert.
    """
    grouped: dict[tuple[str, str], dict[str, AdaptivePoint]] = {}
    for indicator, zones in series.items():
        for zone_id, points in zones.items():
            for point in points:
                grouped.setdefault((zone_id, point.date), {})[indicator] = point

    alerts: list[SeriesAlert] = []
    for (zone_id, date), by_indicator in grouped.items():
        evidence = [
            _evidence(indicator, point, sigma_threshold)
            for indicator, point in by_indicator.items()
            if point.baseline_mean is not None
        ]
        evidence.sort(key=lambda item: INDICATOR_ORDER.index(item.indicator) if item.indicator in INDICATOR_ORDER else 99)
        crossed = [item for item in evidence if item.crossed]
        if not crossed:
            continue
        finite = [abs(item.sigma) for item in crossed if item.sigma is not None]
        infinite = any(item.crossed and item.sigma is None and item.baseline_std == 0 for item in crossed)
        max_abs = math.inf if infinite else (max(finite) if finite else 0.0)
        severity = severity_from_sigma(max_abs, sigma_threshold)
        compound = len(crossed) >= 2
        sample_count = min(item.sample_count for item in crossed)
        quality = quality_by_date.get(date, {})
        confidence, reasons = detection_confidence(
            quality.get("valid_fraction"),
            quality.get("disagreement_fraction"),
            sample_count,
            min_baseline_samples,
        )
        if locations:
            located = locations.get((zone_id, date))
        else:
            located = None
        if located is None:
            lat = lon = polygon = None
            if "zone_geometry_missing" not in reasons:
                reasons.append("zone_geometry_missing")
        else:
            lat, lon, polygon = located
        region = f"{water_body_name} zone {zone_id}"
        indicator_names = [item.indicator for item in crossed]
        template = render_alert_template(
            severity=severity,
            compound=compound,
            evidence=crossed,
            affected_region=region,
            lat=lat,
            lon=lon,
            when=iso_date(date),
            confidence=confidence,
        )
        ordered = [name for name in INDICATOR_ORDER if name in indicator_names]
        alerts.append(
            SeriesAlert(
                id=alert_id(water_body_id, zone_id, date),
                water_body_id=water_body_id,
                water_body_name=water_body_name,
                zone_id=zone_id,
                lat=lat,
                lon=lon,
                polygon=polygon,
                datetime=iso_date(date),
                affected_region=region,
                indicators=ordered,
                compound=compound,
                severity=severity,
                confidence=confidence,
                confidence_reasons=reasons,
                template=template,
                evidence=evidence,
                disclaimer=disclaimer,
            )
        )
    alerts.sort(key=lambda item: (item.datetime, item.zone_id))
    return alerts


def render_alert_template(
    *,
    severity: str,
    compound: bool,
    evidence: list[AlertEvidence],
    affected_region: str,
    lat: float | None,
    lon: float | None,
    when: str,
    confidence: float,
) -> str:
    clauses = [_movement(item) for item in evidence]
    kind = "Compound anomaly" if compound else "Anomaly"
    where = "unlocated zone" if lat is None or lon is None else f"{lat:.5f}, {lon:.5f}"
    return (
        f"{kind} ({severity}): {'; '.join(clauses)} at {affected_region} ({where}) on {when}. "
        f"Confidence {confidence:.2f}. "
        "Relative indexes only. Laboratory verification is required before any operational decision."
    )


def _evidence(indicator: str, point: AdaptivePoint, threshold: float) -> AlertEvidence:
    sigma = None if point.baseline_mean is None else z_score(point.value, point.baseline_mean, point.baseline_std)
    infinite = sigma is not None and not math.isfinite(sigma)
    crossed = False
    if sigma is None:
        crossed = False
    elif infinite:
        crossed = True
    else:
        crossed = abs(sigma) > threshold
    return AlertEvidence(
        indicator=indicator,
        value=float(point.value),
        baseline_mean=float(point.baseline_mean or 0.0),
        baseline_std=point.baseline_std,
        baseline_low=point.baseline_low,
        baseline_high=point.baseline_high,
        sigma=None if sigma is None or infinite else float(sigma),
        threshold=float(threshold),
        crossed=crossed,
        sample_count=int(point.sample_count),
        unit=INDICATOR_UNITS.get(indicator, "index"),
    )


def _movement(item: AlertEvidence) -> str:
    name = _DISPLAY.get(item.indicator, item.indicator)
    if item.sigma is None:
        return f"{name} {item.value:.4g} is far from a zero-variance baseline {item.baseline_mean:.4g}"
    direction = "spike" if item.sigma > 0 else "drop"
    return (
        f"{name} {item.value:.4g} is a {abs(item.sigma):.2f} sigma {direction} "
        f"from baseline {item.baseline_mean:.4g}"
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
