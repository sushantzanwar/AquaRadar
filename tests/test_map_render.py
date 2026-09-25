"""Monitored outlines and a true-color PNG from cached red, green, and blue bands."""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from aquawatch.geo.true_color import true_color_png
from aquawatch.main import create_app


def test_monitored_outlines_cover_the_configured_water_bodies():
    client = TestClient(create_app())
    response = client.get("/api/maps/monitored")
    assert response.status_code == 200
    payload = response.json()
    assert payload["disclaimer"].startswith("Satellite-derived estimate")
    ids = {feature["properties"]["id"] for feature in payload["features"]}
    assert ids == {"demo-reservoir", "demo-lake"}
    assert payload["features"][0]["geometry"]["type"] == "Polygon"


def test_missing_scene_has_no_true_color_render():
    client = TestClient(create_app())
    response = client.get("/api/maps/demo-reservoir/true-color", params={"date": "20240115"})
    assert response.status_code == 404
    assert response.json()["reason"] == "true_color_unavailable"


def test_true_color_png_uses_red_green_and_blue(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    scene = tmp_path / "pond" / "20240115"
    scene.mkdir(parents=True)
    transform = from_origin(0.0, 1.0, 0.1, 0.1)
    _write(rasterio, scene / "B4.tif", np.full((4, 4), 80, dtype=np.float32), transform)
    _write(rasterio, scene / "B3.tif", np.full((4, 4), 40, dtype=np.float32), transform)
    _write(rasterio, scene / "B2.tif", np.full((4, 4), 20, dtype=np.float32), transform)
    rendered = true_color_png(scene)
    assert rendered is not None
    png, bounds = rendered
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    west, south, east, north = bounds
    assert west < east
    assert south < north


def _write(rasterio, path, array, transform):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=array.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as dest:
        dest.write(array, 1)
