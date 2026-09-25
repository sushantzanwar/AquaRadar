"""Confidence and lab-verification fields shared by every public payload."""

from __future__ import annotations

DEFAULT_DISCLAIMER = (
    "AquaWatch reports relative satellite indicators for decision support. "
    "They are not laboratory measurements. Ground sampling and lab verification "
    "are required before any operational or public-health decision."
)


def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def public_stamp(confidence: float, reasons: list[str], disclaimer: str | None = None) -> dict:
    cleaned = []
    for reason in reasons:
        if reason and reason not in cleaned:
            cleaned.append(reason)
    return {
        "confidence": clamp_confidence(confidence),
        "confidence_reasons": cleaned,
        "lab_verification_required": True,
        "disclaimer": disclaimer or DEFAULT_DISCLAIMER,
    }


def merge_confidence(parts: list[tuple[float, list[str]]]) -> tuple[float, list[str]]:
    """Keep the weakest stage. Reasons from every stage that is below 1 are kept."""
    score = 1.0
    reasons: list[str] = []
    for value, stage_reasons in parts:
        score = min(score, clamp_confidence(value))
        for reason in stage_reasons:
            if reason and reason not in reasons:
                reasons.append(reason)
    return score, reasons
