"""Demo-user photo submit and the credit leaderboard."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.domain.schemas import CreditVerdict, Leaderboard, LeaderboardEntry

router = APIRouter()


@router.get("/credits/leaderboard", response_model=Leaderboard)
def leaderboard(state: AppState = Depends(get_state)) -> Leaderboard:
    entries = [LeaderboardEntry(**row) for row in state.credits.leaderboard()]
    return Leaderboard(entries=entries, **state.runner.stamp(1.0, ["not_a_detection"]))


@router.post("/credits/reports", response_model=CreditVerdict)
async def submit_report(
    water_body_id: str = Form(...),
    lon: float = Form(...),
    lat: float = Form(...),
    note: str = Form(""),
    taken_at: str | None = Form(None),
    photo: UploadFile = File(...),
    state: AppState = Depends(get_state),
):
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    data = await photo.read()
    parsed = None
    if taken_at:
        parsed = datetime.fromisoformat(taken_at)
    flagged = _zone_flagged(state, water_body_id, lon, lat)
    result = state.credits.submit(
        water_body_id=water_body_id,
        filename=photo.filename or "photo.jpg",
        data=data,
        lon=lon,
        lat=lat,
        taken_at=parsed,
        note=note,
        zone_is_flagged=flagged,
    )
    if result["accepted"]:
        state.runner.clear_cache()
    reasons = ["photo_check", result["reason"]]
    return CreditVerdict(**result, **state.runner.stamp(1.0 if result["accepted"] else 0.4, reasons))


def _zone_flagged(state: AppState, water_body_id: str, lon: float, lat: float) -> bool:
    from aquawatch.credits.checks import locate

    body = state.settings.body(water_body_id)
    if body is None:
        return False
    zone_id, where = locate(body.boundary, body.zones, lon, lat)
    if where != "inside_zone" or not zone_id:
        return False
    dates = [date for date in body.dates]
    if not dates:
        return False
    analysis = state.runner.analyze(water_body_id, dates[-1])
    zone = next((item for item in analysis.zones if item.zone_id == zone_id), None)
    return bool(zone and zone.anomaly and zone.anomaly.flagged)
