"""Ranked sample sites for one date."""

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.domain.schemas import PriorityList

router = APIRouter()


@router.get("/priority/{water_body_id}/{date}", response_model=PriorityList)
def priority(water_body_id: str, date: str, state: AppState = Depends(get_state)):
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    return state.runner.priority(water_body_id, date)
