"""Deterministic evidence card: why a zone was flagged."""

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.domain.schemas import EvidenceCard

router = APIRouter()


@router.get("/explain/{water_body_id}/{zone_id}/{date}", response_model=EvidenceCard)
def explain(water_body_id: str, zone_id: str, date: str, state: AppState = Depends(get_state)):
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    card = state.runner.evidence(water_body_id, zone_id, date)
    if card is None:
        analysis = state.runner.analyze(water_body_id, date)
        return error_response(state.settings, 404, analysis.status, analysis.reason or "evidence_unavailable")
    return card
