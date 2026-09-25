"""Cloud gate, NDWI disagreement, and extent records. The neural net is not required."""

import ast
from pathlib import Path

import numpy as np

from aquawatch.preprocess.extent import extent_hectares, extent_m2
from aquawatch.preprocess.masking import MIN_VALID_FRACTION, scene_validity
from aquawatch.preprocess.ndwi import disagreement_fraction, low_confidence
from aquawatch.preprocess.store import ExtentStore


def test_scene_below_60_percent_valid_is_insufficient():
    scl = np.array([[6, 8, 9, 6]])
    aoi = np.ones_like(scl, dtype=bool)
    usable, fraction, valid = scene_validity(scl, aoi)
    assert MIN_VALID_FRACTION == 0.60
    assert fraction == 0.5
    assert usable is False
    assert int(valid.sum()) == 2


def test_clear_aoi_passes_the_gate():
    scl = np.array([6, 6, 4, 6, 5])
    aoi = np.ones(5, dtype=bool)
    usable, fraction, _valid = scene_validity(scl, aoi)
    assert fraction == 1.0
    assert usable is True


def test_disagreement_above_a_quarter_of_the_area_is_low_confidence():
    valid = np.ones(4, dtype=bool)
    model = np.array([1, 1, 1, 0], dtype=bool)
    ndwi = np.array([1, 0, 0, 0], dtype=bool)
    fraction = disagreement_fraction(model, ndwi, valid)
    assert fraction == 0.5
    assert low_confidence(fraction) is True
    assert low_confidence(0.25) is False


def test_extent_uses_10m_pixel_area_in_hectares():
    assert extent_m2(250) == 25_000
    assert extent_hectares(250) == 2.5


def test_extent_store_round_trip(tmp_path):
    store = ExtentStore(tmp_path / "water_extent.sqlite")
    store.upsert(
        {
            "water_body_id": "pond",
            "date": "20240101",
            "status": "insufficient_data",
            "valid_fraction": 0.4,
            "disagreement_fraction": None,
            "low_confidence": 0,
            "water_pixels": None,
            "extent_m2": None,
            "extent_ha": None,
            "mask_path": None,
        }
    )
    store.upsert(
        {
            "water_body_id": "pond",
            "date": "20240101",
            "status": "ok",
            "valid_fraction": 0.9,
            "disagreement_fraction": 0.1,
            "low_confidence": 0,
            "water_pixels": 250,
            "extent_m2": 25_000,
            "extent_ha": 2.5,
            "mask_path": "water_mask.tif",
        }
    )
    rows = store.rows()
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["extent_ha"] == 2.5
    parquet = store.write_parquet()
    assert parquet.is_file()


def test_runtime_modules_do_not_import_preprocess():
    root = Path(__file__).resolve().parents[1] / "src" / "aquawatch"
    watched = [root / "main.py", * (root / "api").rglob("*.py"), * (root / "pipeline").rglob("*.py")]
    for path in watched:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("aquawatch.preprocess"), path.name
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("aquawatch.preprocess") for alias in node.names)
