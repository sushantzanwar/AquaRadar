"""Evidence cards stay numeric, and polished text cannot add numbers."""

from aquawatch.domain.schemas import EvidenceCard, IndicatorComparison
from aquawatch.pipeline.alerts import DraftAlert, apply_polish


class StubProvider:
    def __init__(self, name: str, text: str):
        self.name = name
        self.text = text

    def complete(self, prompt: str) -> str:
        return self.text


def _card() -> EvidenceCard:
    return EvidenceCard(
        confidence=0.8,
        confidence_reasons=["baseline_sample_size"],
        disclaimer="Laboratory verification is required.",
        evidence_id="ev-demo-reservoir-north-basin-20241202",
        water_body_id="demo-reservoir",
        zone_id="north-basin",
        zone_name="North basin",
        date="20241202",
        comparisons=[
            IndicatorComparison(
                indicator="turbidity",
                value=14,
                baseline_mean=10,
                baseline_std=1,
                sigma=4,
                threshold=3,
                crossed=True,
                sample_count=40,
                fused=True,
            )
        ],
        extent_m2=1000,
        extent_change_m2=20,
        contributing_indicators=["turbidity"],
        thresholds_crossed=["turbidity>3sigma"],
    )


def _draft() -> DraftAlert:
    return DraftAlert(evidence=_card(), location="Demo Reservoir", severity="warning", indicator="turbidity")


def test_card_carries_confidence_and_disclaimer():
    card = _card()
    assert card.lab_verification_required is True
    assert card.disclaimer
    assert card.confidence == 0.8
    assert card.comparisons[0].value == 14
    assert card.comparisons[0].baseline_mean == 10


def test_polished_wording_keeps_template_fields():
    alert = apply_polish(
        _draft(),
        StubProvider("api", "Turbidity is 14 against a baseline mean of 10 (sigma 4)."),
        _card().disclaimer,
    )
    assert alert.narrative_source == "llm"
    assert alert.polished_summary is not None
    assert alert.indicator == "turbidity"
    assert alert.evidence_id == _card().evidence_id
    assert "Evidence" in alert.template
    assert alert.severity == "warning"


def test_invented_number_is_rejected_and_template_remains():
    alert = apply_polish(
        _draft(),
        StubProvider("api", "Laboratory concentration reached 999."),
        _card().disclaimer,
    )
    assert alert.narrative_source == "llm_rejected"
    assert alert.polished_summary is None
    assert "North basin" in alert.template


def test_disabled_model_uses_the_template_only():
    alert = apply_polish(_draft(), StubProvider("none", "ignored"), _card().disclaimer)
    assert alert.narrative_source == "llm_disabled"
    assert alert.polished_summary is None
    assert alert.template
