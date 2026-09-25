"""Discover cached Sentinel-2 dates for a configured water body."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

DATE_RE = re.compile(r"^\d{8}$")
BODY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

REQUIRED_BANDS = ("B02", "B03", "B04", "B08", "B11", "B12", "SCL")
OPTIONAL_BANDS = ("B05", "B06")
BAND_FILENAMES = {
    "B02": ("B02.tif", "B2.tif"),
    "B03": ("B03.tif", "B3.tif"),
    "B04": ("B04.tif", "B4.tif"),
    "B05": ("B05.tif", "B5.tif"),
    "B06": ("B06.tif", "B6.tif"),
    "B08": ("B08.tif", "B8.tif"),
    "B11": ("B11.tif", "B11.tif"),
    "B12": ("B12.tif", "B12.tif"),
    "SCL": ("SCL.tif", "scl.tif"),
}


def valid_body_id(body_id: str) -> bool:
    return bool(BODY_RE.match(body_id))


def valid_date(date: str) -> bool:
    return bool(DATE_RE.match(date))


def resolve_band(scene_dir: Path, band: str) -> Path | None:
    for name in BAND_FILENAMES[band]:
        path = scene_dir / name
        if path.is_file():
            return path
    return None


def scene_dir(scenes_root: Path, body_id: str, date: str) -> Path:
    return scenes_root / body_id / date


def list_dates(scenes_root: Path, body_id: str, configured: list[str]) -> list[str]:
    """Configured dates plus any extra YYYYMMDD folders a judge dropped in."""
    found: set[str] = set()
    folder = scenes_root / body_id
    if folder.is_dir():
        for child in folder.iterdir():
            if child.is_dir() and valid_date(child.name):
                found.add(child.name)
    for date in configured:
        if valid_date(date):
            found.add(date)
    return sorted(found)


def band_paths(scene: Path) -> tuple[dict[str, Path], list[str]]:
    paths: dict[str, Path] = {}
    missing: list[str] = []
    for band in REQUIRED_BANDS:
        path = resolve_band(scene, band)
        if path is None:
            missing.append(band)
        else:
            paths[band] = path
    for band in OPTIONAL_BANDS:
        path = resolve_band(scene, band)
        if path is not None:
            paths[band] = path
    return paths, missing


def scene_hash(paths: dict[str, Path]) -> str:
    digest = hashlib.sha256()
    for band in sorted(paths):
        path = paths[band]
        stat = path.stat()
        digest.update(band.encode())
        digest.update(str(stat.st_size).encode())
        digest.update(str(stat.st_mtime_ns).encode())
    return digest.hexdigest()[:16]
