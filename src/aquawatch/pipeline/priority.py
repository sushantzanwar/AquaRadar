"""Auditable sample-site ranking."""

from __future__ import annotations

import math


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def _falloff(distance_m: float | None, scale_m: float) -> float:
    if distance_m is None:
        return 0.0
    scale = scale_m if scale_m > 0 else 1.0
    return 1.0 / (1.0 + distance_m / scale)


def proximity_factor(
    distance_to_intake_m: float | None,
    distance_to_settlement_m: float | None,
    intake_weight: float,
    settlement_weight: float,
    scale_m: float,
) -> float:
    return intake_weight * _falloff(distance_to_intake_m, scale_m) + settlement_weight * _falloff(
        distance_to_settlement_m, scale_m
    )


def priority_score(severity: float, persistence: float, proximity: float) -> float:
    return float(severity) * float(persistence) * float(proximity)


def consecutive_anomalous_dates(dates: list[str], anomalous: set[str]) -> int:
    """Trailing run of anomalous dates. ``dates`` is chronological."""
    streak = 0
    for date in reversed(dates):
        if date not in anomalous:
            break
        streak += 1
    return streak


def investigation_formula(intake_weight: float, settlement_weight: float, scale_m: float, z_cap: float) -> str:
    cap = z_cap if z_cap > 0 else 1.0
    scale = scale_m if scale_m > 0 else 1.0
    return (
        "priority = severity × consecutive_anomalous_dates × proximity; "
        f"severity = min(1, max|sigma| / {cap:g}); "
        f"proximity = {intake_weight:g}/(1 + d_intake/{scale:g}) + "
        f"{settlement_weight:g}/(1 + d_settlement/{scale:g})"
    )


def nearest_distance(origin: tuple[float, float], points: list[tuple[float, float]]) -> float | None:
    if not points:
        return None
    return min(haversine_m(origin[0], origin[1], lon, lat) for lon, lat in points)


def formula_text(intake_weight: float, settlement_weight: float, scale_m: float) -> str:
    return (
        "priority = severity × persistence × proximity; "
        f"proximity = {intake_weight:g} × f(distance to nearest intake) + "
        f"{settlement_weight:g} × f(distance to nearest settlement); "
        f"f(d) = 1 / (1 + d / {scale_m:g})"
    )
