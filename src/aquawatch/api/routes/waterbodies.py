"""Zone time series and before/after comparison from one adaptive baseline."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from aquawatch.api.deps import AppState, error_response, get_state
from aquawatch.disclaimer import PRODUCT_DISCLAIMER, public_stamp
from aquawatch.domain.schemas import (
    IndicatorCompare,
    IndicatorSeries,
    WaterBodyCompare,
    WaterBodyTimeSeries,
    ZoneCompare,
    ZoneSeries,
)
from aquawatch.geo.diff import write_raster_diff
from aquawatch.pipeline.temporal import AdaptivePoint, adaptive_series, series_confidence
from aquawatch.storage.zone_series import INDICATOR_ORDER, INDICATOR_REPRESENTATION, INDICATOR_UNITS, load_zone_observations

router = APIRouter()


def _view(state: AppState, water_body_id: str):
    observations = load_zone_observations(
        state.settings.products_store,
        water_body_id,
        state.settings.pixel_area_m2,
    )
    series = adaptive_series(observations)
    flat = [point for zones in series.values() for points in zones.values() for point in points]
    confidence, reasons = series_confidence(flat, state.settings.min_baseline_samples)
    return series, confidence, reasons


def _point(point: AdaptivePoint) -> dict:
    return {
        "date": point.date,
        "value": point.value,
        "baseline_mean": point.baseline_mean,
        "baseline_std": point.baseline_std,
        "baseline_low": point.baseline_low,
        "baseline_high": point.baseline_high,
        "sample_count": point.sample_count,
        "season": point.season,
        "used_fallback": point.used_fallback,
    }


def _indicator_series(series: dict, indicator: str) -> IndicatorSeries:
    zones = []
    for zone_id, points in sorted(series.get(indicator, {}).items()):
        zones.append(ZoneSeries(zone_id=zone_id, points=[_point(point) for point in points]))
    return IndicatorSeries(
        indicator=indicator,  # type: ignore[arg-type]
        unit=INDICATOR_UNITS[indicator],
        representation=INDICATOR_REPRESENTATION[indicator],
        zones=zones,
    )


@router.get("/waterbodies/{water_body_id}/timeseries", response_model=WaterBodyTimeSeries)
def timeseries(water_body_id: str, zone_id: str | None = Query(None), state: AppState = Depends(get_state)):
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    series, confidence, reasons = _view(state, water_body_id)
    if zone_id is not None:
        known = any(zones for zones in series.values())
        series = {
            indicator: {zone: points for zone, points in zones.items() if zone == zone_id}
            for indicator, zones in series.items()
        }
        flat = [point for zones in series.values() for points in zones.values() for point in points]
        confidence, reasons = series_confidence(flat, state.settings.min_baseline_samples)
        if known and not flat:
            confidence = 0.0
            reasons = ["unknown_zone", *reasons]
    indicators = [_indicator_series(series, indicator) for indicator in INDICATOR_ORDER if series.get(indicator)]
    status = "ok" if indicators else "no_observations"
    if indicators:
        reason = None
    elif "unknown_zone" in reasons:
        reason = "unknown_zone"
    else:
        reason = "no_observations"
    return WaterBodyTimeSeries(
        water_body_id=water_body_id,
        status=status,
        reason=reason,
        indicators=indicators,
        **public_stamp(confidence, reasons, PRODUCT_DISCLAIMER),
    )


@router.get("/waterbodies/{water_body_id}/compare", response_model=WaterBodyCompare)
def compare(
    water_body_id: str,
    date1: str = Query(...),
    date2: str = Query(...),
    state: AppState = Depends(get_state),
):
    if state.settings.body(water_body_id) is None:
        return error_response(state.settings, 404, "unusable", "unknown_water_body")
    if not _date_ok(date1) or not _date_ok(date2):
        return error_response(state.settings, 400, "unusable", "invalid_date")
    if date1 == date2:
        return error_response(state.settings, 400, "unusable", "same_date")
    series, confidence, reasons = _view(state, water_body_id)
    indicators = []
    for name in INDICATOR_ORDER:
        zones = series.get(name) or {}
        compared = []
        raster_date1 = None
        raster_date2 = None
        for zone_id, points in sorted(zones.items()):
            by_date = {point.date: point for point in points}
            left = by_date.get(date1)
            right = by_date.get(date2)
            if left is None and right is None:
                continue
            if left and left.raster_path:
                raster_date1 = left.raster_path
            if right and right.raster_path:
                raster_date2 = right.raster_path
            diff = None if left is None or right is None else right.value - left.value
            compared.append(
                ZoneCompare(
                    zone_id=zone_id,
                    date1=None if left is None else _point(left),
                    date2=None if right is None else _point(right),
                    diff=diff,
                )
            )
        diff_raster, diff_mean = _difference_raster(state, water_body_id, name, date1, date2, raster_date1, raster_date2)
        if diff_mean is None and compared:
            numeric = [zone.diff for zone in compared if zone.diff is not None]
            diff_mean = None if not numeric else float(sum(numeric) / len(numeric))
        if compared or diff_raster:
            indicators.append(
                IndicatorCompare(
                    indicator=name,  # type: ignore[arg-type]
                    unit=INDICATOR_UNITS[name],
                    representation=INDICATOR_REPRESENTATION[name],
                    raster_date1=raster_date1,
                    raster_date2=raster_date2,
                    diff_raster=diff_raster,
                    diff_mean=diff_mean,
                    zones=compared,
                )
            )
    paired = any(zone.diff is not None for item in indicators for zone in item.zones)
    status = "ok" if paired else "date_missing"
    reason = None if status == "ok" else "date_not_in_series"
    if status != "ok" and "date_not_in_series" not in reasons:
        reasons = ["date_not_in_series", *reasons]
    return WaterBodyCompare(
        water_body_id=water_body_id,
        date1=date1,
        date2=date2,
        status=status,
        reason=reason,
        indicators=indicators,
        **public_stamp(confidence, reasons, PRODUCT_DISCLAIMER),
    )


def _difference_raster(state: AppState, water_body_id: str, indicator: str, date1: str, date2: str, before: str | None, after: str | None):
    from pathlib import Path

    if indicator == "extent" or not before or not after:
        return None, None
    destination = state.settings.products_store.parent / "diffs" / water_body_id / f"{date1}_{date2}" / f"{indicator}.tif"
    try:
        mean = write_raster_diff(Path(before), Path(after), destination)
    except (OSError, ValueError):
        return None, None
    if mean is None:
        return None, None
    return str(destination), mean


def _date_ok(value: str) -> bool:
    if len(value) != 8 or not value.isdigit():
        return False
    month = int(value[4:6])
    day = int(value[6:8])
    return 1 <= month <= 12 and 1 <= day <= 31
