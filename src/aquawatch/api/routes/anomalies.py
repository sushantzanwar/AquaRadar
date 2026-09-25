"""Zone anomaly scores for one acquisition."""

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.domain.schemas import AnomalyResponse

router = APIRouter()


@router.get("/anomalies/{water_body_id}/{date}", response_model=AnomalyResponse)
def anomalies(water_body_id: str, date: str, state: AppState = Depends(get_state)):
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    return state.runner.anomalies(water_body_id, date)
