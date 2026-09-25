"""Run cloud masking, local water segmentation, and the NDWI cross-check once."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from aquawatch.data.catalog import DataCatalog
from aquawatch.data.loader import load_scene
from aquawatch.preprocess.extent import PIXEL_AREA_M2, extent_hectares, extent_m2
from aquawatch.preprocess.masking import scene_validity
from aquawatch.preprocess.ndwi import disagreement_fraction, low_confidence, ndwi_water
from aquawatch.preprocess.segmenter import MODEL_BANDS, predict_water
from aquawatch.preprocess.store import ExtentStore


def preprocess_catalog(catalog: DataCatalog, model_dir: Path, output_dir: Path, store_path: Path) -> list[dict]:
    store = ExtentStore(store_path)
    written: list[dict] = []
    for body in catalog.bodies:
        for date in body.dates:
            row = preprocess_scene(catalog, body.id, date, model_dir, output_dir)
            store.upsert(row)
            written.append(row)
    store.write_parquet()
    return written


def preprocess_scene(catalog: DataCatalog, water_body_id: str, date: str, model_dir: Path, output_dir: Path) -> dict:
    loaded = load_scene(catalog, water_body_id, date)
    base = {
        "water_body_id": water_body_id,
        "date": date,
        "status": loaded.status,
        "valid_fraction": None,
        "disagreement_fraction": None,
        "low_confidence": 0,
        "water_pixels": None,
        "extent_m2": None,
        "extent_ha": None,
        "mask_path": None,
    }
    if loaded.status in {"missing", "incomplete", "empty_aoi"}:
        return base
    green = np.asarray(loaded.dataset["B3"].values)
    aoi = np.isfinite(green)
    usable, fraction, valid = scene_validity(np.asarray(loaded.dataset["SCL"].values), aoi)
    base["valid_fraction"] = fraction
    if not usable:
        base["status"] = "insufficient_data"
        return base
    image = np.stack([np.asarray(loaded.dataset[band].values) for band in MODEL_BANDS], axis=0)
    model_mask = predict_water(image, model_dir) & valid
    index_mask = ndwi_water(green, np.asarray(loaded.dataset["B8"].values)) & valid
    fraction_differ = disagreement_fraction(model_mask, index_mask, valid)
    flagged = low_confidence(fraction_differ)
    pixels = int(np.count_nonzero(model_mask))
    mask_path = output_dir / water_body_id / date / "water_mask.tif"
    _write_mask(mask_path, model_mask, loaded.dataset)
    base.update(
        {
            "status": "low_confidence" if flagged else "ok",
            "disagreement_fraction": fraction_differ,
            "low_confidence": int(flagged),
            "water_pixels": pixels,
            "extent_m2": extent_m2(pixels, PIXEL_AREA_M2),
            "extent_ha": extent_hectares(pixels, PIXEL_AREA_M2),
            "mask_path": str(mask_path),
        }
    )
    return base


def _write_mask(path: Path, mask: np.ndarray, dataset) -> None:
    import rasterio
    from rasterio.transform import Affine

    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(dataset.x.values, dtype=np.float64)
    y = np.asarray(dataset.y.values, dtype=np.float64)
    dx = float(x[1] - x[0]) if x.size > 1 else 10.0
    dy = float(y[1] - y[0]) if y.size > 1 else -10.0
    transform = Affine(dx, 0.0, float(x[0] - dx / 2), 0.0, dy, float(y[0] - dy / 2))
    crs = dataset.attrs.get("crs") or None
    profile = {
        "driver": "GTiff",
        "height": mask.shape[0],
        "width": mask.shape[1],
        "count": 1,
        "dtype": "uint8",
        "transform": transform,
        "compress": "deflate",
    }
    if crs:
        profile["crs"] = crs
    with rasterio.open(path, "w", **profile) as dest:
        dest.write(mask.astype(np.uint8), 1)
