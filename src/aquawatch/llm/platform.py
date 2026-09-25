"""Text the assistant may quote from the monitored water body.

Numbers come from the stored zone series, series alerts, and the scene evidence
card. They stay relative indexes.
"""

from __future__ import annotations

from aquawatch.domain.schemas import EvidenceCard
from aquawatch.pipeline.anomaly import z_score
from aquawatch.pipeline.temporal import AdaptivePoint
from aquawatch.storage.zone_series import INDICATOR_ORDER, INDICATOR_UNITS

_LABELS = {
    "extent": "extent",
    "turbidity": "turbidity",
    "chlorophyll": "chlorophyll-a",
    "transparency": "transparency",
}


def render_platform(
    *,
    water_body_id: str,
    water_body_name: str,
    date: str | None,
    zone_id: str | None,
    scene_status: str | None,
    scene_reason: str | None,
    series: dict[str, dict[str, list[AdaptivePoint]]],
    alerts: list,
    evidence: EvidenceCard | None,
    sigma_threshold: float,
) -> str:
    lines = [
        (
            f"{water_body_name} ({water_body_id}) is monitored for extent (m²), "
            "turbidity (index), chlorophyll-a (index), and transparency (index)."
        ),
        "These are relative satellite indexes for prioritisation, not laboratory concentrations.",
    ]
    if date and scene_status:
        reason = f" ({scene_reason})" if scene_reason else ""
        lines.append(f"Selected date {date}: scene status {scene_status}{reason}.")
    if zone_id:
        lines.append(f"Selected zone {zone_id}.")
    chosen = _target_date(series, date)
    readings = _readings(series, chosen, zone_id, sigma_threshold)
    if readings:
        lines.append(f"Stored zone series for {chosen}:")
        lines.extend(readings)
    else:
        lines.append("No stored zone series for this water body.")
    if alerts:
        lines.append("Active series alerts:")
        shown = alerts[:10]
        for alert in shown:
            names = ", ".join(_LABELS.get(name, name) for name in alert.indicators)
            lines.append(f"- {alert.severity} · {alert.zone_id} · {alert.datetime[:10]} · {names}. {alert.template}")
        if len(alerts) > len(shown):
            lines.append(f"- {len(alerts) - len(shown)} more alerts are on the feed.")
    else:
        lines.append("No active series alerts.")
    if evidence is not None and evidence.comparisons:
        lines.append(f"Scene evidence for {evidence.zone_name} on {evidence.date}:")
        lines.extend(_comparison_line(row) for row in evidence.comparisons)
        if evidence.contributing_indicators:
            lines.append("Contributing indicators: " + ", ".join(evidence.contributing_indicators) + ".")
    return "\n".join(lines)


def _target_date(series: dict[str, dict[str, list[AdaptivePoint]]], requested: str | None) -> str | None:
    dates = [point.date for zones in series.values() for points in zones.values() for point in points]
    if not dates:
        return requested
    if requested and requested in dates:
        return requested
    return max(dates)


def _readings(
    series: dict[str, dict[str, list[AdaptivePoint]]],
    date: str | None,
    zone_id: str | None,
    sigma_threshold: float,
) -> list[str]:
    if not date:
        return []
    lines = []
    for indicator in INDICATOR_ORDER:
        points = []
        for zone, history in series.get(indicator, {}).items():
            if zone_id and zone != zone_id:
                continue
            match = next((point for point in history if point.date == date), None)
            if match is not None:
                points.append((zone, match))
        if not points:
            continue
        unit = INDICATOR_UNITS[indicator]
        label = _LABELS[indicator]
        if zone_id or len(points) == 1:
            zone, point = points[0]
            lines.append(f"- {_point_line(label, unit, zone, point, sigma_threshold)}")
            continue
        values = [point.value for _zone, point in points]
        flagged = []
        for zone, point in points:
            sigma = z_score(point.value, point.baseline_mean, point.baseline_std) if point.baseline_mean is not None else None
            if sigma is not None and abs(sigma) > sigma_threshold:
                flagged.append(f"{zone} ({_sigma(sigma)})")
        span = f"{min(values):.4g}–{max(values):.4g} {unit}"
        mean = sum(values) / len(values)
        extra = f" Zones past {sigma_threshold:g} sigma: {', '.join(flagged)}." if flagged else " No zone is past the sigma threshold."
        lines.append(
            f"- {label} across {len(points)} zones: mean {mean:.4g} {unit}, range {span}.{extra}"
        )
    return lines


def _point_line(label: str, unit: str, zone: str, point: AdaptivePoint, sigma_threshold: float) -> str:
    sigma = None if point.baseline_mean is None else z_score(point.value, point.baseline_mean, point.baseline_std)
    baseline = "n/a" if point.baseline_mean is None else f"{point.baseline_mean:.4g}"
    std = "n/a" if point.baseline_std is None else f"{point.baseline_std:.4g}"
    crossed = sigma is not None and abs(sigma) > sigma_threshold
    return (
        f"{label} in {zone}: value {point.value:.4g} {unit}, baseline mean {baseline}, "
        f"std {std}, sigma {_sigma(sigma)}, threshold {sigma_threshold:g}, crossed {str(crossed).lower()}."
    )


def _comparison_line(row) -> str:
    sigma = "n/a" if row.sigma is None else f"{row.sigma:.2f}"
    std = "n/a" if row.baseline_std is None else f"{row.baseline_std:.4g}"
    return (
        f"- {row.indicator}: value {row.value:.4g}, baseline mean {row.baseline_mean:.4g}, "
        f"std {std}, sigma {sigma}, threshold {row.threshold:g}, crossed {str(row.crossed).lower()}."
    )


def _sigma(sigma: float | None) -> str:
    if sigma is None:
        return "n/a"
    if sigma != sigma:
        return "n/a"
    if sigma == float("inf") or sigma == float("-inf"):
        return "inf"
    return f"{sigma:.2f}"
