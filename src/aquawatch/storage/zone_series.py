"""Read per-zone extent and indicator means from the preprocess SQLite file.

The API uses this reader instead of importing the preprocess package.
Extent is valid water pixels in the zone times the pixel area, in square metres.
Indicator values are the stored zone means and stay relative indexes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

INDICATOR_ORDER = ("extent", "turbidity", "chlorophyll", "transparency")
INDICATOR_UNITS = {
    "extent": "m2",
    "turbidity": "index",
    "chlorophyll": "index",
    "transparency": "index",
}
INDICATOR_REPRESENTATION = {
    "extent": "water_extent_m2",
    "turbidity": "relative_index",
    "chlorophyll": "relative_index",
    "transparency": "relative_index",
}


def load_zone_observations(path: Path, water_body_id: str, pixel_area_m2: float) -> list[dict]:
    if not path.is_file():
        return []
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "indicator_zones" not in tables:
            return []
        fetched = connection.execute(
            """
            SELECT date, zone_id, indicator, mean, pixel_count, raster_path
            FROM indicator_zones
            WHERE water_body_id = ?
            ORDER BY date, zone_id, indicator
            """,
            (water_body_id,),
        ).fetchall()
    finally:
        connection.close()

    observations: list[dict] = []
    extent_counts: dict[tuple[str, str], int] = {}
    for row in fetched:
        indicator = str(row["indicator"])
        if indicator not in INDICATOR_UNITS or row["mean"] is None:
            continue
        observations.append(
            {
                "zone_id": str(row["zone_id"]),
                "indicator": indicator,
                "date": str(row["date"]),
                "value": float(row["mean"]),
                "raster_path": row["raster_path"],
            }
        )
        key = (str(row["date"]), str(row["zone_id"]))
        extent_counts[key] = max(extent_counts.get(key, 0), int(row["pixel_count"]))
    for (date, zone_id), count in extent_counts.items():
        observations.append(
            {
                "zone_id": zone_id,
                "indicator": "extent",
                "date": date,
                "value": float(count) * float(pixel_area_m2),
                "raster_path": None,
            }
        )
    return observations


def load_scene_quality(path: Path, water_body_id: str) -> dict[str, dict]:
    """Clear-pixel fraction and mask disagreement for each stored date."""
    if not path.is_file():
        return {}
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "water_detection" not in tables:
            return {}
        fetched = connection.execute(
            """
            SELECT date, valid_fraction, disagreement_fraction
            FROM water_detection
            WHERE water_body_id = ?
            """,
            (water_body_id,),
        ).fetchall()
    finally:
        connection.close()
    return {
        str(row["date"]): {
            "valid_fraction": None if row["valid_fraction"] is None else float(row["valid_fraction"]),
            "disagreement_fraction": None
            if row["disagreement_fraction"] is None
            else float(row["disagreement_fraction"]),
        }
        for row in fetched
    }
