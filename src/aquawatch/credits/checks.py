"""GPS, duplicate, and image-fingerprint checks. No accounts."""

from __future__ import annotations

import hashlib
import io
from datetime import datetime

from aquawatch.geo.clip import containing_feature, load_features
from aquawatch.pipeline.priority import haversine_m


def fingerprint(data: bytes) -> str:
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(data)).convert("L").resize((8, 8))
        pixels = list(image.getdata())
        average = sum(pixels) / len(pixels)
        bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
        return "ahash:" + format(int(bits, 2), "x")
    except Exception:
        return "sha256:" + hashlib.sha256(data).hexdigest()


def locate(boundary_path, zone_path, lon: float, lat: float):
    boundary = load_features(boundary_path)
    if containing_feature(boundary, lon, lat) is None:
        return None, "outside_water_boundary"
    zone = containing_feature(load_features(zone_path), lon, lat)
    if zone is None:
        return None, "inside_boundary"
    props = zone.get("properties") or {}
    return str(props.get("id") or props.get("name")), "inside_zone"


def is_duplicate(existing: list[dict], image_hash: str, lon: float, lat: float, taken_at: datetime, distance_m: float, window_s: int) -> bool:
    for row in existing:
        if row["image_hash"] == image_hash:
            return True
        previous = datetime.fromisoformat(row["taken_at"])
        if abs((taken_at - previous).total_seconds()) > window_s:
            continue
        if haversine_m(lon, lat, row["lon"], row["lat"]) <= distance_m:
            return True
    return False
