"""Relative indexes, valid-water intersection, and zone mean/p90."""

from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import Affine

from aquawatch.indicators.compute import (
    INDICATOR_DISCLAIMER,
    INDICATOR_UNIT,
    IndicatorBackendMissing,
    build_zone_series,
    grid_zone_ids,
    load_qda_models,
    relative_indicators,
    zone_statistics,
)
from aquawatch.indicators.rasters import write_indicator_raster
from aquawatch.preprocess.store import ExtentStore


def _models():
    return {
        "turbidity": lambda red: red * 2.0,
        "transparency": lambda green, blue: blue / green,
        "chlorophyll": lambda nir, edge, red: nir - red,
    }


def test_indexes_keep_only_the_valid_water_intersection():
    bands = {
        "B4": np.array([[4.0, 4.0], [4.0, 4.0]]),
        "B3": np.ones((2, 2)),
        "B2": np.full((2, 2), 0.5),
        "B5": np.ones((2, 2)),
        "B6": np.full((2, 2), 3.0),
    }
    water = np.array([[1, 1], [0, 1]])
    scl = np.array([[6, 8], [6, 6]])
    aoi = np.ones((2, 2), dtype=bool)
    grids, rows, reasons = build_zone_series(bands, scl, water, aoi, 1, 1, models=_models())
    assert reasons == []
    assert np.isnan(grids["turbidity"][0, 1])
    assert np.isnan(grids["turbidity"][1, 0])
    assert grids["turbidity"][0, 0] == 8.0
    assert grids["turbidity"][1, 1] == 8.0
    assert rows[0]["indicator"] == "turbidity"
    assert rows[0]["pixel_count"] == 2
    assert rows[0]["mean"] == 8.0
    assert rows[0]["p90"] == 8.0
    assert rows[0]["unit"] == INDICATOR_UNIT
    assert rows[0]["representation"] == "relative_index"
    assert rows[0]["lab_grade"] == 0
    assert rows[0]["model"] == "miller_mckee_2004"
    assert "laboratory" in rows[0]["disclaimer"]
    chlorophyll = next(row for row in rows if row["indicator"] == "chlorophyll")
    assert chlorophyll["mean"] == pytest.approx(-1.0)


def test_zone_grid_reports_mean_and_p90_for_occupied_cells():
    values = np.array([[1.0, 2.0, 10.0, 10.0], [3.0, 4.0, 10.0, np.nan]], dtype=np.float64)
    zones, labels = grid_zone_ids(2, 4, 1, 2)
    assert set(labels.values()) == {"r0c0", "r0c1"}
    rows = zone_statistics(values, zones, labels, "turbidity")
    by_zone = {row["zone_id"]: row for row in rows}
    left = [1.0, 2.0, 3.0, 4.0]
    assert by_zone["r0c0"]["mean"] == pytest.approx(float(np.mean(left)))
    assert by_zone["r0c0"]["p90"] == pytest.approx(float(np.percentile(left, 90)))
    assert by_zone["r0c1"]["pixel_count"] == 3
    assert by_zone["r0c1"]["mean"] == 10.0
    assert by_zone["r0c1"]["disclaimer"] == INDICATOR_DISCLAIMER


def test_missing_red_edge_skips_chlorophyll():
    bands = {"B04": np.ones((2, 2)), "B03": np.ones((2, 2)), "B02": np.ones((2, 2))}
    water = np.ones((2, 2), dtype=bool)
    grids, reasons = relative_indicators(bands, water, models=_models())
    assert "chlorophyll" not in grids
    assert reasons == ["missing_red_edge_bands"]
    assert np.isfinite(grids["transparency"]).all()


def test_indicator_rows_share_the_extent_store(tmp_path):
    store = ExtentStore(tmp_path / "water_extent.sqlite")
    store.upsert(
        {
            "water_body_id": "pond",
            "date": "20240101",
            "status": "ok",
            "valid_fraction": 1.0,
            "disagreement_fraction": 0.0,
            "low_confidence": 0,
            "water_pixels": 4,
            "extent_m2": 400.0,
            "extent_ha": 0.04,
            "mask_path": "water_mask.tif",
        }
    )
    store.replace_indicators(
        "pond",
        "20240101",
        [
            {
                "zone_id": "r0c0",
                "indicator": "turbidity",
                "mean": 1.5,
                "p90": 2.0,
                "pixel_count": 4,
                "unit": "index",
                "representation": "relative_index",
                "lab_grade": 0,
                "model": "miller_mckee_2004",
                "raster_path": "turbidity.tif",
                "disclaimer": INDICATOR_DISCLAIMER,
            }
        ],
    )
    saved = store.indicator_rows()
    assert saved[0]["mean"] == 1.5
    assert saved[0]["unit"] == "index"
    assert store.rows()[0]["extent_ha"] == 0.04
    store.replace_indicators("pond", "20240101", [])
    assert store.indicator_rows() == []
    parquet = store.write_indicator_parquet()
    assert parquet.name == "indicator_zones.parquet"
    assert parquet.is_file()


def test_indicator_raster_is_tagged_as_a_relative_index(tmp_path):
    import rasterio

    path = tmp_path / "turbidity.tif"
    values = np.array([[1.0, np.nan], [2.0, 3.0]], dtype=np.float32)
    write_indicator_raster(path, values, Affine(10, 0, 0, 0, -10, 0), "EPSG:32618", name="turbidity")
    with rasterio.open(path) as source:
        tags = source.tags()
        assert tags["unit"] == "index"
        assert tags["representation"] == "relative_index"
        assert tags["lab_grade"] == "false"
        assert tags["model"] == "miller_mckee_2004"
        assert "laboratory" in tags["disclaimer"]
        assert np.isnan(source.read(1)[0, 1])


def test_preprocess_scene_writes_rasters_and_zone_rows(tmp_path, monkeypatch):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    from aquawatch.data.catalog import load_catalog
    from aquawatch.preprocess.indicators import preprocess_indicator_catalog

    monkeypatch.setattr("aquawatch.indicators.compute.load_qda_models", _models)
    scene = tmp_path / "pond" / "20240101"
    scene.mkdir(parents=True)
    fine = from_origin(0.0, 0.04, 0.01, 0.01)
    for name, value in (("B2.tif", 10), ("B3.tif", 20), ("B4.tif", 30), ("B8.tif", 40)):
        _write_band(rasterio, scene / name, np.full((4, 4), value, dtype=np.float32), fine)
    _write_band(rasterio, scene / "B11.tif", np.full((4, 4), 50, dtype=np.float32), fine)
    _write_band(rasterio, scene / "B12.tif", np.full((4, 4), 60, dtype=np.float32), fine)
    _write_band(rasterio, scene / "SCL.tif", np.full((4, 4), 6, dtype=np.uint8), fine)
    catalog = load_catalog()
    body = catalog.body("demo-reservoir")
    local = type(catalog)(
        root=tmp_path,
        boundary_crs="EPSG:4326",
        bodies=(
            type(body)(
                id="pond",
                name="Pond",
                boundary={
                    "type": "Polygon",
                    "coordinates": [[[0.0, 0.0], [0.02, 0.0], [0.02, 0.04], [0.0, 0.04], [0.0, 0.0]]],
                },
                dates=("20240101",),
            ),
        ),
    )
    mask_dir = tmp_path / "masks"
    mask = np.zeros((4, 2), dtype=np.uint8)
    mask[:, 0] = 1
    mask_path = mask_dir / "pond" / "20240101" / "water_mask.tif"
    mask_path.parent.mkdir(parents=True)
    _write_band(rasterio, mask_path, mask, from_origin(0.0, 0.04, 0.01, 0.01))
    results = preprocess_indicator_catalog(local, mask_dir, tmp_path / "indicators", tmp_path / "water_extent.sqlite", 1, 1)
    assert results[0].status == "ok"
    assert Path(results[0].rasters["turbidity"]).is_file()
    assert "chlorophyll" not in results[0].rasters
    turbidity = next(row for row in results[0].zones if row["indicator"] == "turbidity")
    assert turbidity["pixel_count"] == 4
    assert turbidity["mean"] == pytest.approx(60.0)
    assert turbidity["unit"] == "index"
    from aquawatch.preprocess.store import ExtentStore

    stored = ExtentStore(tmp_path / "water_extent.sqlite").indicator_rows()
    assert stored[0]["representation"] == "relative_index"
    assert (tmp_path / "indicator_zones.parquet").is_file()


def _write_band(rasterio, path, array, transform):
    path.parent.mkdir(parents=True, exist_ok=True)
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


def test_missing_qda_backend_is_reported(monkeypatch):
    import sys

    monkeypatch.delitem(sys.modules, "qda_modelos", raising=False)
    monkeypatch.delitem(sys.modules, "qda_modelos.chlorophylla", raising=False)
    monkeypatch.delitem(sys.modules, "qda_modelos.total_suspended_solids_turbidity", raising=False)
    monkeypatch.delitem(sys.modules, "qda_modelos.water_transparency", raising=False)
    real_import = __import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "qda_modelos" or name.startswith("qda_modelos."):
            raise ImportError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(IndicatorBackendMissing):
        load_qda_models()
