"""One-time indicator rasters and zone statistics for cached scenes.

Uses the water mask from the extent step. Indexes are computed only where
that mask intersects clear SCL pixels inside the AOI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from aquawatch.data.catalog import DataCatalog
from aquawatch.data.loader import load_scene
from aquawatch.indicators.compute import INDICATOR_DISCLAIMER, build_zone_series
from aquawatch.indicators.rasters import affine_from_centers, write_indicator_raster
from aquawatch.preprocess.masking import scene_validity
from aquawatch.preprocess.store import ExtentStore

_RED_EDGE = {
    "B5": ("B5.tif", "B05.tif", "B5.tiff", "B05.tiff"),
    "B6": ("B6.tif", "B06.tif", "B6.tiff", "B06.tiff"),
}


@dataclass
class IndicatorSceneResult:
    water_body_id: str
    date: str
    status: str
    reasons: list[str] = field(default_factory=list)
    rasters: dict[str, str] = field(default_factory=dict)
    zones: list[dict] = field(default_factory=list)


def preprocess_indicator_catalog(
    catalog: DataCatalog,
    mask_dir: Path,
    output_dir: Path,
    store_path: Path,
    zone_rows: int = 4,
    zone_cols: int = 4,
) -> list[IndicatorSceneResult]:
    store = ExtentStore(store_path)
    written: list[IndicatorSceneResult] = []
    for body in catalog.bodies:
        for date in body.dates:
            result = preprocess_indicator_scene(
                catalog,
                body.id,
                date,
                mask_dir,
                output_dir,
                zone_rows=zone_rows,
                zone_cols=zone_cols,
            )
            store.replace_indicators(result.water_body_id, result.date, result.zones)
            written.append(result)
    store.write_indicator_parquet()
    return written


def preprocess_indicator_scene(
    catalog: DataCatalog,
    water_body_id: str,
    date: str,
    mask_dir: Path,
    output_dir: Path,
    zone_rows: int = 4,
    zone_cols: int = 4,
) -> IndicatorSceneResult:
    loaded = load_scene(catalog, water_body_id, date)
    result = IndicatorSceneResult(water_body_id, date, loaded.status, [loaded.reason] if loaded.reason else [])
    if loaded.status in {"missing", "incomplete", "empty_aoi"}:
        return result
    green = np.asarray(loaded.dataset["B3"].values)
    aoi = np.isfinite(green)
    usable, _fraction, _valid = scene_validity(np.asarray(loaded.dataset["SCL"].values), aoi)
    if not usable:
        result.status = "insufficient_data"
        result.reasons = ["valid_fraction_below_cutoff"]
        return result
    mask_path = mask_dir / water_body_id / date / "water_mask.tif"
    if not mask_path.is_file():
        result.status = "water_mask_missing"
        result.reasons = ["water_mask_missing"]
        return result
    water_mask = _read_mask(mask_path)
    if water_mask.shape != green.shape:
        result.status = "shape_mismatch"
        result.reasons = ["water_mask_shape_mismatch"]
        return result
    bands = {
        "B2": np.asarray(loaded.dataset["B2"].values),
        "B3": green,
        "B4": np.asarray(loaded.dataset["B4"].values),
    }
    scene_dir = catalog.scene_dir(water_body_id, date)
    red_edge, red_edge_reason = _optional_red_edge(scene_dir, green.shape, loaded.dataset)
    bands.update(red_edge)
    grids, rows, reasons = build_zone_series(
        bands,
        np.asarray(loaded.dataset["SCL"].values),
        water_mask,
        aoi,
        zone_rows,
        zone_cols,
    )
    if red_edge_reason:
        reasons = [red_edge_reason, *reasons]
    transform = affine_from_centers(loaded.dataset.x.values, loaded.dataset.y.values)
    crs = loaded.dataset.attrs.get("crs") or None
    raster_paths: dict[str, str] = {}
    for name, values in grids.items():
        path = output_dir / water_body_id / date / f"{name}.tif"
        write_indicator_raster(path, values, transform, crs, name=name)
        raster_paths[name] = str(path)
    for row in rows:
        row["raster_path"] = raster_paths[row["indicator"]]
        row["disclaimer"] = INDICATOR_DISCLAIMER
    result.status = "ok" if any(np.isfinite(grid).any() for grid in grids.values()) else "no_water"
    result.reasons = reasons
    result.rasters = raster_paths
    result.zones = rows
    return result


def _read_mask(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as source:
        return source.read(1)


def _optional_red_edge(scene_dir: Path, shape: tuple[int, int], dataset) -> tuple[dict[str, np.ndarray], str | None]:
    found: dict[str, np.ndarray] = {}
    for band, names in _RED_EDGE.items():
        path = next((scene_dir / name for name in names if (scene_dir / name).is_file()), None)
        if path is None:
            return {}, None
        array = _read_aligned_band(path, shape, dataset)
        if array is None:
            return {}, "red_edge_grid_mismatch"
        found[band] = array
    return found, None


def _read_aligned_band(path: Path, shape: tuple[int, int], dataset) -> np.ndarray | None:
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(path) as source:
        data = source.read(1)
        if data.shape == shape:
            return data.astype(np.float64)
        crs = dataset.attrs.get("crs") or None
        if not crs or source.crs is None:
            return None
        destination = np.full(shape, np.nan, dtype=np.float32)
        reproject(
            source=data,
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=affine_from_centers(dataset.x.values, dataset.y.values),
            dst_crs=crs,
            resampling=Resampling.bilinear,
        )
        return destination.astype(np.float64)
