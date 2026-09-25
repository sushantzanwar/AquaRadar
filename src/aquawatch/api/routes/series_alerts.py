"""Alerts derived on request from the stored zone time series."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.disclaimer import PRODUCT_DISCLAIMER, public_stamp
from aquawatch.domain.schemas import (
    AlertEvidenceCard,
    InvestigationList,
    SamplePoint,
    SeriesAlertList,
    SeriesAlertModel,
)
from aquawatch.geo.zones import zone_location
from aquawatch.pipeline.investigation import context_points, rank_active_zones
from aquawatch.pipeline.series_alerts import (
    SeriesAlert,
    alert_evidence_view,
    build_series_alerts,
    parse_alert_id,
)
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
        **public_stamp(alert.confidence, alert.confidence_reasons, PRODUCT_DISCLAIMER),
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
        **public_stamp(confidence, reasons, PRODUCT_DISCLAIMER),
    )


@router.get("/alerts/{alert_id}/evidence", response_model=AlertEvidenceCard)
def alert_evidence(alert_id: str, state: AppState = Depends(get_state)):
    match = _find_alert(alert_id, state)
    if not isinstance(match, SeriesAlert):
        return match
    _water_body_id, _zone_id, date = parse_alert_id(alert_id) or ("", "", "")
    quality = load_scene_quality(state.settings.products_store, match.water_body_id).get(date, {})
    view = alert_evidence_view(match, quality.get("valid_fraction"), quality.get("disagreement_fraction"))
    return AlertEvidenceCard(
        **view,
        **public_stamp(match.confidence, match.confidence_reasons, PRODUCT_DISCLAIMER),
    )


def _find_alert(alert_id: str, state: AppState) -> SeriesAlert | object:
    parsed = parse_alert_id(alert_id)
    if parsed is None:
        return error_response(state.settings, 404, "unusable", "unknown_alert")
    water_body_id, _zone_id, _date = parsed
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    match = next((alert for alert in alerts_for_settings(state, water_body_id) if alert.id == alert_id), None)
    if match is None:
        return error_response(state.settings, 404, "unusable", "unknown_alert")
    return match


@router.get("/alerts/{alert_id}", response_model=SeriesAlertModel)
def get_alert(alert_id: str, state: AppState = Depends(get_state)):
    match = _find_alert(alert_id, state)
    if not isinstance(match, SeriesAlert):
        return match
    return _model(match)


@router.get("/waterbodies/{water_body_id}/priorities", response_model=InvestigationList)
def priorities(water_body_id: str, state: AppState = Depends(get_state)):
    body = state.settings.body(water_body_id)
    if body is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    alerts = _alerts_for_body(state, body.id, body.name)
    observations = load_zone_observations(
        state.settings.products_store,
        water_body_id,
        state.settings.pixel_area_m2,
    )
    observed: dict[str, set[str]] = {}
    for row in observations:
        observed.setdefault(str(row["zone_id"]), set()).add(str(row["date"]))
    ranked, formula = rank_active_zones(
        alerts,
        {zone_id: sorted(dates) for zone_id, dates in observed.items()},
        intakes=context_points(getattr(body, "intakes", None), water_body_id),
        settlements=context_points(getattr(body, "settlements", None), water_body_id),
        intake_weight=body.intake_weight,
        settlement_weight=body.settlement_weight,
        scale_m=body.proximity_scale_m,
        z_cap=state.settings.z_cap,
        sigma_threshold=state.settings.sigma_threshold,
    )
    if not ranked:
        confidence, reasons = 1.0, ["relative_index", "no_anomalies"]
    else:
        confidence = min(zone.confidence for zone in ranked)
        reasons = []
        for zone in ranked:
            for reason in zone.confidence_reasons:
                if reason not in reasons:
                    reasons.append(reason)
    return InvestigationList(
        water_body_id=water_body_id,
        formula=formula,
        zones=[
            {
                "rank": zone.rank,
                "zone_id": zone.zone_id,
                "date": zone.date,
                "severity": zone.severity,
                "severity_label": zone.severity_label,
                "max_abs_sigma": zone.max_abs_sigma,
                "persistence": zone.persistence,
                "proximity": zone.proximity,
                "distance_to_intake_m": zone.distance_to_intake_m,
                "distance_to_settlement_m": zone.distance_to_settlement_m,
                "priority": zone.priority,
                "sample_point": SamplePoint(lat=zone.sample_lat, lon=zone.sample_lon),
                "indicators": zone.indicators,
                "confidence": zone.confidence,
                "confidence_reasons": zone.confidence_reasons,
            }
            for zone in ranked
        ],
        **public_stamp(confidence, reasons, PRODUCT_DISCLAIMER),
    )
