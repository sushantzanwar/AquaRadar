"""Sigma flags, compound zones, and alerts read from the stored series."""

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from aquawatch.api.deps import get_state
from aquawatch.api.routes import series_alerts
from aquawatch.indicators.rasters import write_indicator_raster
from aquawatch.pipeline.series_alerts import build_series_alerts, severity_from_sigma
from aquawatch.pipeline.temporal import AdaptivePoint
from aquawatch.preprocess.store import ExtentStore

DISCLAIMER = "Relative index only. Laboratory verification is required."


def _point(date, value, mean, std, count=8):
    band = 0.0 if std is None else std
    return AdaptivePoint(
        date=date,
        value=value,
        baseline_mean=mean,
        baseline_std=std,
        baseline_low=mean - band,
        baseline_high=mean + band,
        sample_count=count,
        season="DJF",
        used_fallback=False,
    )


def _alerts(series, quality=None, threshold=3, min_samples=8):
    return build_series_alerts(
        "pond",
        "Pond",
        series,
        quality or {"20240115": {"valid_fraction": 1.0, "disagreement_fraction": 0.0}},
        sigma_threshold=threshold,
        min_baseline_samples=min_samples,
        disclaimer=DISCLAIMER,
    )


def test_three_sigma_is_quiet_and_past_it_is_flagged():
    quiet = _alerts({"turbidity": {"r0c0": [_point("20240115", 13, 10, 1)]}})
    flagged = _alerts({"turbidity": {"r0c0": [_point("20240115", 13.1, 10, 1)]}})
    assert quiet == []
    assert flagged[0].indicators == ["turbidity"]
    assert flagged[0].compound is False
    assert flagged[0].severity == "low"
    assert flagged[0].evidence[0].sigma == pytest.approx(3.1)
    assert flagged[0].evidence[0].crossed is True
    assert "Laboratory verification" in flagged[0].template
    assert "13.1" in flagged[0].template
    assert "10" in flagged[0].template


def test_severity_steps_with_sigma_magnitude():
    assert severity_from_sigma(3.1, 3) == "low"
    assert severity_from_sigma(4.5, 3) == "med"
    assert severity_from_sigma(6, 3) == "high"


def test_extent_drop_and_chlorophyll_spike_are_one_compound_alert():
    series = {
        "extent": {"r0c0": [_point("20240115", 100, 1000, 100)]},
        "chlorophyll": {"r0c0": [_point("20240115", 8, 2, 1)]},
        "turbidity": {"r0c0": [_point("20240115", 2, 2, 1)]},
    }
    alerts = _alerts(
        series,
        {"20240115": {"valid_fraction": 0.8, "disagreement_fraction": 0.25}},
        min_samples=4,
    )
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.compound is True
    assert alert.indicators == ["extent", "chlorophyll"]
    assert alert.severity == "high"
    assert alert.confidence == pytest.approx(0.75)
    assert "valid_pixel_fraction" in alert.confidence_reasons
    assert "mask_agreement" in alert.confidence_reasons
    assert alert.template.startswith("Compound anomaly")
    assert "drop" in alert.template
    assert "spike" in alert.template
    extent = next(item for item in alert.evidence if item.indicator == "extent")
    assert extent.sigma == pytest.approx(-9)
    chlorophyll = next(item for item in alert.evidence if item.indicator == "chlorophyll")
    assert chlorophyll.sigma == pytest.approx(6)
    assert "chlorophyll-a" in alert.template


def test_alerts_are_computed_from_the_store(tmp_path):
    raster = tmp_path / "turbidity.tif"
    write_indicator_raster(
        raster,
        np.ones((2, 2), dtype=np.float32),
        from_origin(0, 2, 1, 1),
        "EPSG:4326",
        name="turbidity",
    )
    store = ExtentStore(tmp_path / "water_extent.sqlite")
    history = ("20200115", "20200215", "20201215")
    for date in history:
        store.upsert(
            {
                "water_body_id": "pond",
                "date": date,
                "status": "ok",
                "valid_fraction": 0.5,
                "disagreement_fraction": 0.1,
                "low_confidence": 0,
                "water_pixels": 10,
                "extent_m2": 1000,
                "extent_ha": 0.1,
                "mask_path": "water_mask.tif",
            }
        )
        store.replace_indicators("pond", date, [_indicator(10.0, 10, raster)])
    store.upsert(
        {
            "water_body_id": "pond",
            "date": "20240115",
            "status": "ok",
            "valid_fraction": 0.5,
            "disagreement_fraction": 0.1,
            "low_confidence": 0,
            "water_pixels": 2,
            "extent_m2": 200,
            "extent_ha": 0.02,
            "mask_path": "water_mask.tif",
        }
    )
    store.replace_indicators("pond", "20240115", [_indicator(40.0, 2, raster)])

    client = _client(store.sqlite_path)
    listed = client.get("/alerts")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body["alerts"]) == 1
    alert = body["alerts"][0]
    assert alert["id"] == "sa-pond-r0c0-20240115"
    assert alert["compound"] is True
    assert alert["severity"] == "high"
    assert set(alert["indicators"]) == {"extent", "turbidity"}
    assert alert["confidence"] == pytest.approx(0.5)
    assert alert["lat"] == pytest.approx(1)
    assert alert["lon"] == pytest.approx(1)
    assert alert["polygon"]["type"] == "Polygon"
    assert "Laboratory verification" in alert["template"]
    fetched = client.get(f"/api/alerts/{alert['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["template"] == alert["template"]
    assert client.get("/alerts/sa-pond-r0c0-20200115").status_code == 404
    assert client.get("/alerts/not-an-alert").status_code == 404


def _indicator(mean, pixels, raster):
    return {
        "zone_id": "r0c0",
        "indicator": "turbidity",
        "mean": mean,
        "p90": mean,
        "pixel_count": pixels,
        "unit": "index",
        "representation": "relative_index",
        "lab_grade": 0,
        "model": "miller_mckee_2004",
        "raster_path": str(raster),
        "disclaimer": DISCLAIMER,
    }


def _client(store_path):
    class Body:
        id = "pond"
        name = "Pond"

    class Settings:
        products_store = store_path
        pixel_area_m2 = 100.0
        zone_rows = 1
        zone_cols = 1
        sigma_threshold = 3.0
        min_baseline_samples = 2
        disclaimer = DISCLAIMER
        water_bodies = [Body()]

        def body(self, water_body_id):
            return Body() if water_body_id == "pond" else None

    class State:
        settings = Settings()

    app = FastAPI()
    app.include_router(series_alerts.router)
    app.include_router(series_alerts.router, prefix="/api")
    app.dependency_overrides[get_state] = lambda: State()
    return TestClient(app)
