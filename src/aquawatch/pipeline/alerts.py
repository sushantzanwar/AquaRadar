"""Template alerts, with optional wording that cannot invent new numbers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from aquawatch.domain.schemas import Alert, EvidenceCard
from aquawatch.pipeline.anomaly import severity_label

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def iso_date(date: str) -> str:
    return f"{date[:4]}-{date[4:6]}-{date[6:8]}T00:00:00Z"


def render_template(
    *,
    severity: str,
    indicator: str,
    region: str,
    location: str,
    when: str,
    confidence: float,
    evidence_id: str,
) -> str:
    return (
        f"{severity.capitalize()} relative {indicator} signal at {region}, {location}, on {when}. "
        f"Confidence {confidence:.2f}. Evidence {evidence_id}. "
        "Laboratory verification is required before any operational decision."
    )


def numbers_in_text(text: str) -> list[float]:
    return [float(match) for match in NUMBER_RE.findall(text)]


def allowed_numbers(card: EvidenceCard, extra: list[float] | None = None) -> list[float]:
    allowed = list(extra or [])
    allowed.append(card.confidence)
    if card.extent_m2 is not None:
        allowed.append(card.extent_m2)
    if card.extent_change_m2 is not None:
        allowed.append(card.extent_change_m2)
    for row in card.comparisons:
        allowed.extend([row.value, row.baseline_mean, row.threshold, float(row.sample_count)])
        if row.baseline_std is not None:
            allowed.append(row.baseline_std)
        if row.sigma is not None:
            allowed.append(row.sigma)
            allowed.append(abs(row.sigma))
    if len(card.date) == 8 and card.date.isdigit():
        allowed.extend([float(card.date[:4]), float(card.date[4:6]), float(card.date[6:8])])
    return allowed


def narrative_respects_evidence(text: str, card: EvidenceCard) -> bool:
    allowed = allowed_numbers(card)
    for number in numbers_in_text(text):
        if not any(math_close(number, candidate) for candidate in allowed):
            return False
    return True


def math_close(left: float, right: float) -> bool:
    gap = abs(left - right)
    # Allow rounding, and reject a nearby but different figure such as 999 vs 1000.
    return gap <= 1e-6 or (gap < 1 and gap <= max(0.05, abs(right) * 0.001))


@dataclass
class DraftAlert:
    evidence: EvidenceCard
    location: str
    severity: str
    indicator: str


def dominant_indicator(card: EvidenceCard) -> tuple[str, str]:
    crossed = [row for row in card.comparisons if row.crossed and row.fused and row.sigma is not None]
    if not crossed:
        return "turbidity", "watch"
    top = max(crossed, key=lambda row: abs(row.sigma or 0))
    return top.indicator, severity_label(abs(top.sigma or 0))


def build_alert(draft: DraftAlert, disclaimer: str, polish: str | None, source: str) -> Alert:
    card = draft.evidence
    template = render_template(
        severity=draft.severity,
        indicator=draft.indicator,
        region=card.zone_name,
        location=draft.location,
        when=iso_date(card.date),
        confidence=card.confidence,
        evidence_id=card.evidence_id,
    )
    return Alert(
        confidence=card.confidence,
        confidence_reasons=list(card.confidence_reasons),
        disclaimer=disclaimer,
        alert_id=f"al-{card.water_body_id}-{card.zone_id}-{card.date}-{draft.indicator}",
        evidence_id=card.evidence_id,
        water_body_id=card.water_body_id,
        location=draft.location,
        datetime=iso_date(card.date),
        affected_region=card.zone_name,
        indicator=draft.indicator,
        severity=draft.severity,  # type: ignore[arg-type]
        template=template,
        polished_summary=polish,
        narrative_source=source,  # type: ignore[arg-type]
    )


def apply_polish(draft: DraftAlert, provider, disclaimer: str) -> Alert:
    card = draft.evidence
    if provider.name == "none":
        return build_alert(draft, disclaimer, None, "llm_disabled")
    prompt = (
        "Rewrite the alert in plain language. Use only the numbers in the evidence JSON. "
        "Do not name a pollutant or a laboratory concentration.\n"
        f"Template: {render_template(severity=draft.severity, indicator=draft.indicator, region=card.zone_name, location=draft.location, when=iso_date(card.date), confidence=card.confidence, evidence_id=card.evidence_id)}\n"
        f"Evidence: {card.model_dump_json()}"
    )
    try:
        text = provider.complete(prompt).strip()
    except Exception:
        return build_alert(draft, disclaimer, None, "llm_unreachable")
    if not text or not narrative_respects_evidence(text, card):
        return build_alert(draft, disclaimer, None, "llm_rejected")
    return build_alert(draft, disclaimer, text, "llm")
