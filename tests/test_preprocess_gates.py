"""Valid-pixel gate, SWIR grid alignment, and the runtime/script boundary."""

import ast
from pathlib import Path

import numpy as np

from aquawatch.geo.cloud_mask import insufficient_data, valid_fraction, valid_pixel_mask
from aquawatch.geo.resample import grids_match, upsample_nearest


def test_valid_fraction_below_cutoff_is_insufficient():
    assert insufficient_data(0.39, 0.4) is True
    assert insufficient_data(0.4, 0.4) is False


def test_scl_drops_cloud_and_keeps_water():
    scl = np.array([0, 6, 8, 4, 3])
    mask = valid_pixel_mask(scl)
    assert mask.tolist() == [False, True, False, True, False]
    assert valid_fraction(mask) == 0.4


def test_swir_upsample_aligns_only_with_the_reference_grid():
    swir = np.ones((2, 3))
    resampled = upsample_nearest(swir, 2)
    assert resampled.shape == (4, 6)
    assert grids_match(resampled.shape, (4, 6))
    assert grids_match(resampled.shape, (5, 6)) is False


def test_runtime_package_does_not_import_scripts():
    root = Path(__file__).resolve().parents[1] / "src" / "aquawatch"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not name.startswith("scripts"), f"{path} imports {name}"
