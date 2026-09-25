"""Open one cached Sentinel-2 date."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


@dataclass
class BandStack:
    water_body_id: str
    date: str
    acquired_at: datetime
    paths: dict[str, Path]
    arrays: dict[str, np.ndarray]
    transforms: dict[str, object]
    crs: object
    reference_band: str = "B02"
    profile: dict = field(default_factory=dict)

    def reference(self) -> np.ndarray:
        return self.arrays[self.reference_band]


def acquisition_time(date: str) -> datetime:
    return datetime.strptime(date, "%Y%m%d").replace(tzinfo=timezone.utc)


def read_stack(water_body_id: str, date: str, paths: dict[str, Path]) -> BandStack:
    import rasterio

    arrays: dict[str, np.ndarray] = {}
    transforms: dict[str, object] = {}
    crs = None
    profile: dict = {}
    for band, path in paths.items():
        with rasterio.open(path) as source:
            arrays[band] = np.squeeze(source.read(1))
            transforms[band] = source.transform
            crs = source.crs
            if band == "B02":
                profile = {
                    "driver": "GTiff",
                    "height": source.height,
                    "width": source.width,
                    "count": 1,
                    "dtype": "float32",
                    "crs": source.crs,
                    "transform": source.transform,
                }
    dataset = _as_dataset(arrays, transforms.get("B02"), crs)
    if dataset is not None:
        profile["dataset_bands"] = list(dataset.data_vars)
    return BandStack(
        water_body_id=water_body_id,
        date=date,
        acquired_at=acquisition_time(date),
        paths=paths,
        arrays=arrays,
        transforms=transforms,
        crs=crs,
        profile=profile,
    )


def _as_dataset(arrays, transform, crs):
    try:
        import xarray as xr
    except ImportError:
        return None
    data = {name: (("y", "x"), array) for name, array in arrays.items()}
    return xr.Dataset(data, attrs={"crs": str(crs) if crs is not None else "", "transform": str(transform)})
