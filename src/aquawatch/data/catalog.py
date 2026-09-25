"""Water-body definitions for the offline scene loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from aquawatch.settings import repo_root


@dataclass(frozen=True)
class MonitoredWaterBody:
    id: str
    name: str
    boundary: dict
    dates: tuple[str, ...]


@dataclass(frozen=True)
class DataCatalog:
    root: Path
    boundary_crs: str
    bodies: tuple[MonitoredWaterBody, ...]

    def body(self, water_body_id: str) -> MonitoredWaterBody:
        for item in self.bodies:
            if item.id == water_body_id:
                return item
        raise KeyError(water_body_id)

    def scene_dir(self, water_body_id: str, date: str) -> Path:
        return self.root / water_body_id / date


def load_catalog(path: Path | None = None, root: Path | None = None) -> DataCatalog:
    repo = (root or repo_root()).resolve()
    catalog_path = path or (repo / "config" / "data_catalog.yaml")
    with catalog_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    data_root = Path(raw.get("root", "data"))
    if not data_root.is_absolute():
        data_root = repo / data_root
    bodies = []
    for item in raw.get("water_bodies", []):
        geometry = item["boundary"]
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"{item['id']} boundary must be a GeoJSON Polygon or MultiPolygon")
        bodies.append(
            MonitoredWaterBody(
                id=str(item["id"]),
                name=str(item["name"]),
                boundary=geometry,
                dates=tuple(str(date) for date in item.get("dates", [])),
            )
        )
    return DataCatalog(
        root=data_root,
        boundary_crs=str(raw.get("boundary_crs", "EPSG:4326")),
        bodies=tuple(bodies),
    )
