"""Inject a plume into a copy of a cached scene and run the normal pipeline."""

from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends

from aquawatch.api.deps import AppState, get_state
from aquawatch.domain.schemas import PlumeRequest, StressResponse
from aquawatch.geo.catalog import scene_dir
from aquawatch.pipeline.stress import copy_scene, inject_plume

router = APIRouter()


@router.post("/stress/plume", response_model=StressResponse)
def plume(body: PlumeRequest, state: AppState = Depends(get_state)):
    settings = state.settings
    if settings.body(body.water_body_id) is None:
        return StressResponse(
            water_body_id=body.water_body_id,
            date=body.date,
            status="unusable",
            reason="unknown_water_body",
            **state.runner.stamp(0.0, ["unknown_water_body"]),
        )
    source = scene_dir(settings.scenes_dir, body.water_body_id, body.date)
    if not source.is_dir():
        return StressResponse(
            water_body_id=body.water_body_id,
            date=body.date,
            status="missing",
            reason="scene_folder_missing",
            **state.runner.stamp(0.0, ["scene_missing"]),
        )
    temporary = Path(tempfile.mkdtemp(prefix="aquawatch-plume-"))
    try:
        destination = temporary / body.water_body_id / body.date
        copy_scene(source, destination)
        located = _pixel(destination, body.lon, body.lat, body.radius_m)
        if located is None:
            return StressResponse(
                water_body_id=body.water_body_id,
                date=body.date,
                status="unusable",
                reason="plume_outside_scene",
                **state.runner.stamp(0.0, ["plume_outside_scene"]),
            )
        row, col, radius_px = located
        try:
            inject_plume(
                destination,
                indicator=body.indicator,
                row=row,
                col=col,
                radius_px=radius_px,
                magnitude=body.magnitude,
            )
        except FileNotFoundError:
            return StressResponse(
                water_body_id=body.water_body_id,
                date=body.date,
                status="unusable",
                reason="chlorophyll_requires_red_edge" if body.indicator == "chlorophyll" else "driving_band_missing",
                **state.runner.stamp(0.0, ["driving_band_missing"]),
            )
        anomalies = state.runner.anomalies(body.water_body_id, body.date, temporary)
        alerts = state.runner.alerts(body.water_body_id, body.date, temporary)
        priority = state.runner.priority(body.water_body_id, body.date, temporary)
        evidence = []
        for zone in anomalies.zones:
            card = state.runner.evidence(body.water_body_id, zone.zone_id, body.date, temporary)
            if card is not None:
                evidence.append(card)
        return StressResponse(
            water_body_id=body.water_body_id,
            date=body.date,
            status=anomalies.status,
            reason=anomalies.reason,
            anomalies=anomalies,
            alerts=alerts,
            evidence=evidence,
            priority=priority,
            **state.runner.stamp(anomalies.confidence, [*anomalies.confidence_reasons, "synthetic_plume"]),
        )
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _pixel(scene: Path, lon: float, lat: float, radius_m: float):
    import rasterio
    from rasterio.transform import rowcol

    band = next((scene / name for name in ("B02.tif", "B2.tif") if (scene / name).is_file()), None)
    if band is None:
        return None
    with rasterio.open(band) as source:
        row, col = rowcol(source.transform, lon, lat)
        if not (0 <= row < source.height and 0 <= col < source.width):
            return None
        pixel = abs(float(source.transform.a))
        if pixel < 1:
            pixel = pixel * 111_320.0 * math.cos(math.radians(lat))
        radius_px = radius_m / pixel if pixel else 1
        return int(row), int(col), float(radius_px)
