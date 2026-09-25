"""Sigma flags and multi-indicator fusion. This module does not read rasters."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class IndicatorSample:
    indicator: str
    value: float
    mean: float
    std: float | None
    sample_count: int


@dataclass
class ComparisonRow:
    indicator: str
    value: float
    baseline_mean: float
    baseline_std: float | None
    sigma: float | None
    threshold: float
    crossed: bool
    sample_count: int
    fused: bool


@dataclass
class ZoneAnomaly:
    flagged: bool
    fused_score: float
    contributing: list[str]
    comparisons: list[ComparisonRow]
    confidence: float
    confidence_reasons: list[str] = field(default_factory=list)
    severity_label: str | None = None
    max_abs_sigma: float = 0.0


def z_score(value: float, mean: float, std: float | None) -> float | None:
    if std is None:
        return None
    if std <= 0:
        if value == mean:
            return 0.0
        return math.inf
    return (value - mean) / std


def severity_label(max_abs_sigma: float) -> str:
    if max_abs_sigma > 5:
        return "severe"
    if max_abs_sigma > 4:
        return "warning"
    return "watch"


def normalized_severity(max_abs_sigma: float, z_cap: float) -> float:
    if not math.isfinite(max_abs_sigma):
        return 1.0
    cap = z_cap if z_cap > 0 else 1.0
    return max(0.0, min(1.0, max_abs_sigma / cap))


def evaluate_zone(
    samples: list[IndicatorSample],
    *,
    sigma_threshold: float,
    weights: dict[str, float],
    min_baseline_samples: int,
    z_cap: float = 6.0,
) -> ZoneAnomaly:
    rows: list[ComparisonRow] = []
    reasons: list[str] = []
    for sample in samples:
        sigma = z_score(sample.value, sample.mean, sample.std)
        fused = weights.get(sample.indicator, 0.0) > 0
        infinite = sigma is not None and not math.isfinite(sigma)
        if sigma is None:
            crossed = False
            reasons.append("baseline_std_missing")
        else:
            crossed = abs(sigma) > sigma_threshold
            if infinite:
                reasons.append("zero_baseline_std")
        rows.append(
            ComparisonRow(
                indicator=sample.indicator,
                value=float(sample.value),
                baseline_mean=float(sample.mean),
                baseline_std=None if sample.std is None else float(sample.std),
                sigma=None if sigma is None or infinite else float(sigma),
                threshold=float(sigma_threshold),
                crossed=bool(crossed),
                sample_count=int(sample.sample_count),
                fused=fused,
                # infinite z still counts as a cross for fused indicators
            )
        )
        if infinite and fused:
            rows[-1].crossed = True

    weight_sum = 0.0
    fused_total = 0.0
    for row, sample in zip(rows, samples):
        weight = weights.get(row.indicator, 0.0)
        sigma = z_score(sample.value, sample.mean, sample.std)
        if weight <= 0 or sigma is None:
            continue
        magnitude = z_cap if not math.isfinite(sigma) else min(abs(sigma), z_cap)
        fused_total += weight * magnitude
        weight_sum += weight
    fused_score = fused_total / weight_sum if weight_sum else 0.0
    contributing = [row.indicator for row in rows if row.crossed and row.fused]
    flagged = bool(contributing)
    finite_sigmas = [abs(row.sigma) for row in rows if row.indicator in contributing and row.sigma is not None]
    infinite_cross = any(row.indicator in contributing and row.sigma is None and row.baseline_std == 0 for row in rows)
    max_abs = z_cap if infinite_cross else (max(finite_sigmas) if finite_sigmas else 0.0)

    confidence = 1.0
    counts = [sample.sample_count for sample in samples]
    if counts and min(counts) < min_baseline_samples:
        confidence = max(min(counts), 0) / float(min_baseline_samples)
        reasons.append("baseline_sample_size")
    if not samples:
        confidence = 0.0
        reasons.append("no_indicators")

    label = severity_label(max_abs) if flagged else None
    return ZoneAnomaly(
        flagged=flagged,
        fused_score=float(fused_score),
        contributing=contributing,
        comparisons=rows,
        confidence=max(0.0, min(1.0, confidence)),
        confidence_reasons=list(dict.fromkeys(reasons)),
        severity_label=label,
        max_abs_sigma=float(max_abs if flagged else 0.0),
    )
