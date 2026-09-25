"""Zone GeoJSON for the map and the before/after pair used by the swipe control."""

from fastapi import APIRouter, Depends, Query

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.domain.schemas import TrendSeries
from aquawatch.geo.clip import feature_id, load_features

router = APIRouter()


def _features(state: AppState, body_id: str, date: str):
    body = state.settings.body(body_id)
    if body is None:
        return None
    analysis = state.runner.analyze(body_id, date)
    by_id = {zone.zone_id: zone for zone in analysis.zones}
    features = []
    for index, feature in enumerate(load_features(body.zones), start=1):
        zone_id = feature_id(feature, f"zone-{index}")
        zone = by_id.get(zone_id)
        properties = dict(feature.get("properties") or {})
        properties.update(
            {
                "id": zone_id,
                "date": date,
                "status": analysis.status,
                "reason": analysis.reason,
                "flagged": bool(zone and zone.anomaly and zone.anomaly.flagged),
                "fused_score": None if zone is None or zone.anomaly is None else zone.anomaly.fused_score,
                "severity_label": None if zone is None or zone.anomaly is None else zone.anomaly.severity_label,
                "confidence": analysis.confidence if zone is None or zone.anomaly is None else zone.anomaly.confidence,
                "disclaimer": state.settings.disclaimer,
                "lab_verification_required": True,
                "means": {} if zone is None else zone.means,
            }
        )
        features.append({"type": "Feature", "properties": properties, "geometry": feature.get("geometry")})
    return {
        "type": "FeatureCollection",
        "features": features,
        "confidence": analysis.confidence,
        "confidence_reasons": analysis.confidence_reasons,
        "lab_verification_required": True,
        "disclaimer": state.settings.disclaimer,
        "status": analysis.status,
        "reason": analysis.reason,
        "scene_extent_m2": analysis.scene_extent_m2,
    }


@router.get("/maps/{water_body_id}/zones")
def zones(
    water_body_id: str,
    date: str = Query(...),
    compare: str | None = Query(None),
    state: AppState = Depends(get_state),
):
    current = _features(state, water_body_id, date)
    if current is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    payload = {"date": current}
    if compare:
        other = _features(state, water_body_id, compare)
        payload["compare"] = other
    payload.update(
        {
            "confidence": current["confidence"],
            "confidence_reasons": current["confidence_reasons"],
            "lab_verification_required": True,
            "disclaimer": state.settings.disclaimer,
        }
    )
    return payload


@router.get("/maps/{water_body_id}/trends", response_model=TrendSeries)
def trends(
    water_body_id: str,
    zone_id: str = Query(...),
    indicator: str = Query("turbidity"),
    state: AppState = Depends(get_state),
) -> TrendSeries:
    if state.settings.body(water_body_id) is None:
        return TrendSeries(
            water_body_id=water_body_id,
            zone_id=zone_id,
            indicator=indicator,
            points=[],
            **state.runner.stamp(0.0, ["unknown_water_body"]),
        )
    return state.runner.trends(water_body_id, zone_id, indicator)
