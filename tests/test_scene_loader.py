"""Offline scene catalog and analysis-ready loader."""

import numpy as np
import pytest

from aquawatch.data.catalog import load_catalog
from aquawatch.data.loader import BANDS, SCL_SENTINEL, load_scene


def test_catalog_lists_id_name_boundary_and_dates():
    catalog = load_catalog()
    reservoir = catalog.body("demo-reservoir")
    assert reservoir.name == "Demo Reservoir"
    assert reservoir.boundary["type"] == "Polygon"
    assert "20241202" in reservoir.dates
    assert catalog.scene_dir("demo-reservoir", "20241202").name == "20241202"


def test_missing_scene_returns_sentinel_values():
    catalog = load_catalog()
    loaded = load_scene(catalog, "demo-reservoir", "20241202")
    assert loaded.status == "missing"
    assert loaded.reason == "scene_folder_missing"
    assert loaded.dataset.sizes["band"] == len(BANDS)
    assert np.isnan(loaded.dataset["B2"].values).all()
    assert np.isnan(loaded.dataset["stack"].sel(band="B11").values).all()
    assert int(loaded.dataset["SCL"].values.flat[0]) == SCL_SENTINEL
    assert loaded.dataset.attrs["offline"] == "true"


def test_loader_stacks_resamples_and_clips(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    scene = tmp_path / "pond" / "20240101"
    scene.mkdir(parents=True)
    fine = from_origin(0.0, 0.04, 0.01, 0.01)
    coarse = from_origin(0.0, 0.04, 0.02, 0.02)
    _write(rasterio, scene / "B2.tif", np.full((4, 4), 10, dtype=np.float32), fine)
    _write(rasterio, scene / "B3.tif", np.full((4, 4), 20, dtype=np.float32), fine)
    _write(rasterio, scene / "B4.tif", np.full((4, 4), 30, dtype=np.float32), fine)
    _write(rasterio, scene / "B8.tif", np.full((4, 4), 40, dtype=np.float32), fine)
    _write(rasterio, scene / "B11.tif", np.full((2, 2), 50, dtype=np.float32), coarse)
    _write(rasterio, scene / "B12.tif", np.full((2, 2), 60, dtype=np.float32), coarse)
    _write(rasterio, scene / "SCL.tif", np.full((4, 4), 6, dtype=np.uint8), fine)

    catalog = load_catalog()
    body = catalog.body("demo-reservoir")
    clipped = type(body)(
        id="pond",
        name="Pond",
        boundary={
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [0.02, 0.0], [0.02, 0.04], [0.0, 0.04], [0.0, 0.0]]],
        },
        dates=("20240101",),
    )
    local = type(catalog)(root=tmp_path, boundary_crs="EPSG:4326", bodies=(clipped,))
    loaded = load_scene(local, "pond", "20240101")
    assert loaded.status == "ok"
    stack = loaded.dataset["stack"]
    assert stack.sizes["band"] == 7
    assert stack.sizes["x"] == 2
    assert stack.sizes["y"] == 4
    assert np.allclose(loaded.dataset["B11"].values, 50)
    assert np.allclose(loaded.dataset["B2"].values, 10)
    assert set(np.unique(loaded.dataset["SCL"].values)) == {6}


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
