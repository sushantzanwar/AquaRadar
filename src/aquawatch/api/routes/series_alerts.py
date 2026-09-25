"""Alerts derived on request from the stored zone time series."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.disclaimer import public_stamp
from aquawatch.domain.schemas import SeriesAlertList, SeriesAlertModel
from aquawatch.geo.zones import zone_location
from aquawatch.pipeline.series_alerts import SeriesAlert, build_series_alerts, parse_alert_id
from aquawatch.pipeline.temporal import adaptive_series
from aquawatch.storage.zone_series import load_scene_quality, load_zone_observations

router = APIRouter()


def alerts_for_settings(state: AppState, water_body_id: str | None = None) -> list[SeriesAlert]:
    bodies = state.settings.water_bodies
    if water_body_id is not None:
        body = state.settings.body(water_body_id)
        bodies = [] if body is None else [body]
    found: list[SeriesAlert] = []
    for body in bodies:
        found.extend(_alerts_for_body(state, body.id, body.name))
    found.sort(key=lambda item: (item.datetime, item.water_body_id, item.zone_id), reverse=True)
    return found


def _alerts_for_body(state: AppState, water_body_id: str, water_body_name: str) -> list[SeriesAlert]:
    observations = load_zone_observations(
        state.settings.products_store,
        water_body_id,
        state.settings.pixel_area_m2,
    )
    series = adaptive_series(observations)
    locations = _locations(series, state.settings.zone_rows, state.settings.zone_cols)
    return build_series_alerts(
        water_body_id,
        water_body_name,
        series,
        load_scene_quality(state.settings.products_store, water_body_id),
        sigma_threshold=state.settings.sigma_threshold,
        min_baseline_samples=state.settings.min_baseline_samples,
        disclaimer=state.settings.disclaimer,
        locations=locations,
    )


def _locations(series, n_rows: int, n_cols: int) -> dict[tuple[str, str], tuple[float, float, dict] | None]:
    located: dict[tuple[str, str], tuple[float, float, dict] | None] = {}
    for zones in series.values():
        for zone_id, points in zones.items():
            for point in points:
                key = (zone_id, point.date)
                if key in located or not point.raster_path:
                    continue
                try:
                    located[key] = zone_location(Path(point.raster_path), zone_id, n_rows, n_cols)
                except (OSError, ValueError):
                    located[key] = None
    return located


def _model(alert: SeriesAlert) -> SeriesAlertModel:
    return SeriesAlertModel(
        id=alert.id,
        water_body_id=alert.water_body_id,
        water_body_name=alert.water_body_name,
        zone_id=alert.zone_id,
        lat=alert.lat,
        lon=alert.lon,
        polygon=alert.polygon,
        datetime=alert.datetime,
        affected_region=alert.affected_region,
        indicators=alert.indicators,
        compound=alert.compound,
        severity=alert.severity,  # type: ignore[arg-type]
        template=alert.template,
        evidence=[item.__dict__ for item in alert.evidence],
        **public_stamp(alert.confidence, alert.confidence_reasons, alert.disclaimer),
    )


@router.get("/alerts", response_model=SeriesAlertList)
def list_alerts(state: AppState = Depends(get_state)):
    alerts = alerts_for_settings(state)
    if not alerts:
        confidence, reasons = 1.0, ["relative_index", "no_anomalies"]
    else:
        confidence = min(alert.confidence for alert in alerts)
        reasons = []
        for alert in alerts:
            for reason in alert.confidence_reasons:
                if reason not in reasons:
                    reasons.append(reason)
    return SeriesAlertList(
        alerts=[_model(alert) for alert in alerts],
        **public_stamp(confidence, reasons, state.settings.disclaimer),
    )


@router.get("/alerts/{alert_id}", response_model=SeriesAlertModel)
def get_alert(alert_id: str, state: AppState = Depends(get_state)):
    parsed = parse_alert_id(alert_id)
    if parsed is None:
        return error_response(state.settings, 404, "unusable", "unknown_alert")
    water_body_id, _zone_id, _date = parsed
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    match = next((alert for alert in alerts_for_settings(state, water_body_id) if alert.id == alert_id), None)
    if match is None:
        return error_response(state.settings, 404, "unusable", "unknown_alert")
    return _model(match)
