"""Seasonal leave-one-out baselines, shared by the chart and compare APIs."""

import math

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import Affine

from aquawatch.api.deps import get_state
from aquawatch.api.routes import waterbodies
from aquawatch.indicators.rasters import write_indicator_raster
from aquawatch.pipeline.temporal import adaptive_series, series_confidence
from aquawatch.preprocess.store import ExtentStore
from aquawatch.storage.zone_series import load_zone_observations

DISCLAIMER = "Relative index only. Laboratory verification is required."


def _obs(zone, indicator, date, value, raster=None):
    return {
        "zone_id": zone,
        "indicator": indicator,
        "date": date,
        "value": value,
        "raster_path": raster,
    }


def test_seasonal_baseline_ignores_the_other_season_and_the_date_itself():
    rows = [
        _obs("r0c0", "turbidity", "20240115", 10),
        _obs("r0c0", "turbidity", "20240215", 12),
        _obs("r0c0", "turbidity", "20241215", 14),
        _obs("r0c0", "turbidity", "20240715", 100),
    ]
    points = adaptive_series(rows)["turbidity"]["r0c0"]
    winter = next(point for point in points if point.date == "20240115")
    summer = next(point for point in points if point.date == "20240715")
    assert winter.season == "DJF"
    assert winter.used_fallback is False
    assert winter.sample_count == 2
    assert winter.baseline_mean == pytest.approx(13)
    assert winter.baseline_std == pytest.approx(math.sqrt(2))
    assert winter.baseline_low == pytest.approx(13 - math.sqrt(2))
    assert winter.baseline_high == pytest.approx(13 + math.sqrt(2))
    assert summer.used_fallback is True
    assert summer.baseline_mean == pytest.approx(12)
    assert summer.sample_count == 3


def test_thin_history_lowers_confidence():
    points = adaptive_series(
        [
            _obs("r0c0", "transparency", "20240301", 1),
            _obs("r0c0", "transparency", "20240401", 2),
            _obs("r0c0", "transparency", "20240501", 3),
        ]
    )["transparency"]["r0c0"]
    confidence, reasons = series_confidence(points, min_baseline_samples=8)
    assert confidence == pytest.approx(2 / 8)
    assert "baseline_sample_size" in reasons
    assert "relative_index" in reasons


def test_extent_and_indexes_share_one_series(tmp_path):
    store = ExtentStore(tmp_path / "water_extent.sqlite")
    store.replace_indicators(
        "pond",
        "20240115",
        [
            {
                "zone_id": "r0c0",
                "indicator": "turbidity",
                "mean": 4.0,
                "p90": 5.0,
                "pixel_count": 10,
                "unit": "index",
                "representation": "relative_index",
                "lab_grade": 0,
                "model": "miller_mckee_2004",
                "raster_path": "turbidity.tif",
                "disclaimer": DISCLAIMER,
            }
        ],
    )
    store.replace_indicators(
        "pond",
        "20240715",
        [
            {
                "zone_id": "r0c0",
                "indicator": "turbidity",
                "mean": 8.0,
                "p90": 9.0,
                "pixel_count": 20,
                "unit": "index",
                "representation": "relative_index",
                "lab_grade": 0,
                "model": "miller_mckee_2004",
                "raster_path": "later.tif",
                "disclaimer": DISCLAIMER,
            }
        ],
    )
    observations = load_zone_observations(store.sqlite_path, "pond", pixel_area_m2=100)
    series = adaptive_series(observations)
    turbidity = {point.date: point for point in series["turbidity"]["r0c0"]}
    extent = {point.date: point for point in series["extent"]["r0c0"]}
    assert turbidity["20240715"].value == 8
    assert turbidity["20240715"].baseline_mean == 4
    assert extent["20240115"].value == 1000
    assert extent["20240715"].value == 2000
    assert extent["20240715"].baseline_mean == 1000


def test_timeseries_and_compare_use_the_same_baseline(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    before = tmp_path / "before.tif"
    after = tmp_path / "after.tif"
    transform = Affine(10, 0, 0, 0, -10, 0)
    write_indicator_raster(before, np.array([[1.0, 1.0], [1.0, np.nan]], dtype=np.float32), transform, "EPSG:32618", name="turbidity")
    write_indicator_raster(after, np.array([[4.0, 4.0], [4.0, np.nan]], dtype=np.float32), transform, "EPSG:32618", name="turbidity")
    store = ExtentStore(tmp_path / "water_extent.sqlite")
    _row = {
        "zone_id": "r0c0",
        "indicator": "turbidity",
        "p90": 1.0,
        "pixel_count": 3,
        "unit": "index",
        "representation": "relative_index",
        "lab_grade": 0,
        "model": "miller_mckee_2004",
        "disclaimer": DISCLAIMER,
    }
    store.replace_indicators("pond", "20240115", [{**_row, "mean": 1.0, "raster_path": str(before)}])
    store.replace_indicators("pond", "20240215", [{**_row, "mean": 3.0, "raster_path": str(after)}])
    store.replace_indicators("pond", "20240315", [{**_row, "mean": 5.0, "raster_path": str(after)}])

    client = _client(tmp_path / "water_extent.sqlite")
    chart = client.get("/waterbodies/pond/timeseries")
    assert chart.status_code == 200
    body = chart.json()
    turbidity = next(item for item in body["indicators"] if item["indicator"] == "turbidity")
    assert turbidity["unit"] == "index"
    assert turbidity["representation"] == "relative_index"
    january = next(point for point in turbidity["zones"][0]["points"] if point["date"] == "20240115")
    assert january["baseline_mean"] == pytest.approx(4)
    assert january["baseline_low"] == january["baseline_mean"] - january["baseline_std"]

    compared = client.get("/api/waterbodies/pond/compare", params={"date1": "20240115", "date2": "20240215"})
    assert compared.status_code == 200
    payload = compared.json()
    assert payload["status"] == "ok"
    indicator = next(item for item in payload["indicators"] if item["indicator"] == "turbidity")
    zone = indicator["zones"][0]
    assert zone["diff"] == pytest.approx(2)
    assert zone["date1"]["baseline_mean"] == january["baseline_mean"]
    assert zone["date1"]["baseline_low"] == january["baseline_low"]
    assert zone["date1"]["baseline_high"] == january["baseline_high"]
    assert indicator["diff_mean"] == pytest.approx(3)
    assert indicator["diff_raster"]
    with rasterio.open(indicator["diff_raster"]) as source:
        tags = source.tags()
        assert tags["unit"] == "index"
        assert tags["lab_grade"] == "false"
        assert np.isnan(source.read(1)[1, 1])
    extent = next(item for item in payload["indicators"] if item["indicator"] == "extent")
    assert extent["unit"] == "m2"
    assert extent["diff_raster"] is None
    assert client.get("/waterbodies/missing/timeseries").status_code == 404
    assert client.get("/waterbodies/pond/compare", params={"date1": "20240115", "date2": "20240115"}).status_code == 400


def _client(store_path):
    class Settings:
        products_store = store_path
        pixel_area_m2 = 100.0
        min_baseline_samples = 8
        disclaimer = DISCLAIMER

        def body(self, water_body_id):
            return object() if water_body_id == "pond" else None

    class State:
        settings = Settings()

    app = FastAPI()
    app.include_router(waterbodies.router)
    app.include_router(waterbodies.router, prefix="/api")
    app.dependency_overrides[get_state] = lambda: State()
    return TestClient(app)
