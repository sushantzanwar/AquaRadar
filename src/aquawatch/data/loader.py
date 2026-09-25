"""Stack cached Sentinel-2 L2A bands into an analysis-ready cube.

Reads only local GeoTIFFs. A date with no scene folder still returns a dataset
filled with sentinel values and status ``missing``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aquawatch.data.catalog import DataCatalog, MonitoredWaterBody

BANDS = ("B2", "B3", "B4", "B8", "B11", "B12", "SCL")
REFLECTANCE_BANDS = ("B2", "B3", "B4", "B8", "B11", "B12")
SWIR_BANDS = ("B11", "B12")
REFLECTANCE_SENTINEL = float("nan")
SCL_SENTINEL = 0

_FILENAMES = {
    "B2": ("B2.tif", "B02.tif", "B2.tiff", "B02.tiff"),
    "B3": ("B3.tif", "B03.tif", "B3.tiff", "B03.tiff"),
    "B4": ("B4.tif", "B04.tif", "B4.tiff", "B04.tiff"),
    "B8": ("B8.tif", "B08.tif", "B8.tiff", "B08.tiff"),
    "B11": ("B11.tif", "B11.tiff"),
    "B12": ("B12.tif", "B12.tiff"),
    "SCL": ("SCL.tif", "scl.tif", "SCL.tiff"),
}


@dataclass(frozen=True)
class LoadedScene:
    water_body_id: str
    date: str
    status: str
    reason: str | None
    dataset: object

    @property
    def present(self) -> bool:
        return self.status == "ok"


def load_scenes(catalog: DataCatalog, water_body_id: str) -> list[LoadedScene]:
    body = catalog.body(water_body_id)
    return [load_scene(catalog, water_body_id, date) for date in body.dates]


def load_scene(catalog: DataCatalog, water_body_id: str, date: str) -> LoadedScene:
    body = catalog.body(water_body_id)
    folder = catalog.scene_dir(water_body_id, date)
    if not folder.is_dir():
        return LoadedScene(
            water_body_id,
            date,
            "missing",
            "scene_folder_missing",
            _sentinel_dataset(body, date, "missing", "scene_folder_missing"),
        )
    paths = {band: _resolve(folder, band) for band in BANDS}
    missing = [band for band, path in paths.items() if path is None]
    reference_path = paths.get("B2") or paths.get("B3") or paths.get("B4") or paths.get("B8")
    if reference_path is None:
        return LoadedScene(
            water_body_id,
            date,
            "incomplete",
            "missing_reference_band",
            _sentinel_dataset(body, date, "incomplete", "missing_reference_band"),
        )
    arrays, transform, crs, height, width = _read_aligned(paths, reference_path)
    arrays, transform, height, width = _clip(arrays, transform, crs, height, width, body.boundary, catalog.boundary_crs)
    status = "incomplete" if missing else "ok"
    reason = None if not missing else "missing_bands:" + ",".join(missing)
    if not np.any(np.isfinite(arrays["B2"])):
        status = "empty_aoi"
        reason = reason or "aoi_outside_scene"
    return LoadedScene(water_body_id, date, status, reason, _dataset(body, date, arrays, transform, crs, height, width, status, reason))


def _resolve(folder, band):
    for name in _FILENAMES[band]:
        path = folder / name
        if path.is_file():
            return path
    return None


def _sentinel_for(band: str) -> float:
    return float(SCL_SENTINEL) if band == "SCL" else REFLECTANCE_SENTINEL


def _sentinel_dataset(body: MonitoredWaterBody, date: str, status: str, reason: str):
    arrays = {band: np.full((1, 1), _sentinel_for(band), dtype=np.float32) for band in BANDS}
    return _dataset(body, date, arrays, None, None, 1, 1, status, reason)


def _read_aligned(paths, reference_path):
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(reference_path) as reference:
        height, width = reference.height, reference.width
        transform = reference.transform
        crs = reference.crs
        profile_crs = reference.crs
    arrays = {}
    for band in BANDS:
        path = paths.get(band)
        if path is None:
            fill = _sentinel_for(band)
            arrays[band] = np.full((height, width), fill, dtype=np.float32)
            continue
        with rasterio.open(path) as source:
            data = source.read(1)
            same_grid = data.shape == (height, width) and source.transform == transform and source.crs == profile_crs
            if same_grid:
                arrays[band] = data.astype(np.float32)
                continue
            destination = np.full((height, width), _sentinel_for(band), dtype=np.float32)
            resampling = Resampling.nearest if band in {"SCL", *SWIR_BANDS} else Resampling.bilinear
            reproject(
                source=data,
                destination=destination,
                src_transform=source.transform,
                src_crs=source.crs,
                dst_transform=transform,
                dst_crs=crs,
                resampling=resampling,
            )
            arrays[band] = destination
    return arrays, transform, crs, height, width


def _clip(arrays, transform, crs, height, width, boundary, boundary_crs):
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom

    geometry = boundary
    if crs is not None and str(crs) != boundary_crs:
        geometry = transform_geom(boundary_crs, crs, boundary)
    inside = geometry_mask([geometry], out_shape=(height, width), transform=transform, invert=True)
    if not np.any(inside):
        sentinel = {band: np.full((1, 1), _sentinel_for(band), dtype=np.float32) for band in BANDS}
        return sentinel, None, 1, 1
    for band, values in arrays.items():
        fill = _sentinel_for(band)
        arrays[band] = np.where(inside, values, fill).astype(np.float32)
    rows = np.any(inside, axis=1)
    cols = np.any(inside, axis=0)
    row_idx = np.flatnonzero(rows)
    col_idx = np.flatnonzero(cols)
    cropped = {band: values[np.ix_(rows, cols)] for band, values in arrays.items()}
    from rasterio.windows import Window
    from rasterio.windows import transform as window_transform

    window = Window(int(col_idx[0]), int(row_idx[0]), int(col_idx.size), int(row_idx.size))
    return cropped, window_transform(window, transform), int(row_idx.size), int(col_idx.size)


def _dataset(body, date, arrays, transform, crs, height, width, status, reason):
    import xarray as xr

    if transform is None:
        xs = np.array([0.0], dtype=np.float64)
        ys = np.array([0.0], dtype=np.float64)
    else:
        xs = transform.c + (np.arange(width) + 0.5) * transform.a
        ys = transform.f + (np.arange(height) + 0.5) * transform.e
    stack = np.stack([arrays[band] for band in BANDS], axis=0).astype(np.float32)
    variables = {band: (("y", "x"), arrays[band]) for band in BANDS}
    variables["stack"] = (("band", "y", "x"), stack)
    return xr.Dataset(
        variables,
        coords={"y": ("y", ys), "x": ("x", xs), "band": ("band", list(BANDS))},
        attrs={
            "water_body_id": body.id,
            "water_body_name": body.name,
            "date": date,
            "status": status,
            "reason": reason or "",
            "crs": "" if crs is None else str(crs),
            "offline": "true",
            "reflectance_sentinel": "nan",
            "scl_sentinel": str(SCL_SENTINEL),
        },
    )
