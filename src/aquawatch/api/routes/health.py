"""Liveness and a listing of which cached dates are on disk."""

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, get_state
from aquawatch.domain.schemas import HealthBody, HealthResponse
from aquawatch.geo.catalog import list_dates, scene_dir

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(state: AppState = Depends(get_state)) -> HealthResponse:
    bodies = []
    for body in state.settings.water_bodies:
        on_disk = []
        for date in list_dates(state.settings.scenes_dir, body.id, body.dates):
            folder = scene_dir(state.settings.scenes_dir, body.id, date)
            if folder.is_dir():
                on_disk.append(date)
        bodies.append(
            HealthBody(id=body.id, name=body.name, configured_dates=list(body.dates), dates_on_disk=on_disk)
        )
    return HealthResponse(
        status="ok",
        water_bodies=bodies,
        **state.runner.stamp(1.0, ["not_a_detection"]),
    )
