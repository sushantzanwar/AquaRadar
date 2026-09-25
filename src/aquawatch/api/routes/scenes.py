"""Configured water bodies and the status of every cached date."""

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, get_state
from aquawatch.domain.schemas import SceneIndex, WaterBodyOverview
from aquawatch.geo.catalog import list_dates

router = APIRouter()


@router.get("/scenes", response_model=SceneIndex)
def scenes(state: AppState = Depends(get_state)) -> SceneIndex:
    overviews = []
    index_confidence = 1.0
    index_reasons = ["not_a_detection"]
    for body in state.settings.water_bodies:
        dates = []
        latest_alert = None
        latest_ok = None
        confidences = [1.0]
        reasons = ["not_a_detection"]
        for date in list_dates(state.settings.scenes_dir, body.id, body.dates):
            status = state.runner.scene_status(body, date)
            dates.append(status)
            confidences.append(status.confidence)
            reasons.extend(status.confidence_reasons)
            if status.status == "ok":
                latest_ok = date
        if latest_ok is not None:
            feed = state.runner.alerts(body.id, latest_ok)
            if feed.alerts:
                latest_alert = feed.alerts[0]
        body_confidence = min(confidences)
        index_confidence = min(index_confidence, body_confidence)
        index_reasons.extend(reasons)
        overviews.append(
            WaterBodyOverview(
                id=body.id,
                name=body.name,
                dates=dates,
                latest_alert=latest_alert,
                **state.runner.stamp(body_confidence, reasons),
            )
        )
    return SceneIndex(water_bodies=overviews, **state.runner.stamp(index_confidence, index_reasons))
