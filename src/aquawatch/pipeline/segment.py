"""Water mask from the local UNet++ model, cross-checked with NDWI."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from aquawatch.geo.tiles import iter_windows, stitch_votes
from aquawatch.settings import Settings


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    green = green.astype(np.float64)
    nir = nir.astype(np.float64)
    denom = green + nir
    with np.errstate(divide="ignore", invalid="ignore"):
        index = (green - nir) / denom
    return np.where(denom == 0, np.nan, index)


def ndwi_mask(green: np.ndarray, nir: np.ndarray, threshold: float) -> np.ndarray:
    index = ndwi(green, nir)
    return np.isfinite(index) & (index > threshold)


def agreement_fraction(model_mask: np.ndarray, index_mask: np.ndarray, valid: np.ndarray) -> float:
    both = valid & np.isfinite(model_mask.astype(float))
    if not np.any(both):
        return 0.0
    return float(np.mean(model_mask[both] == index_mask[both]))


def water_extent_m2(mask: np.ndarray, pixel_area: float) -> float:
    return float(np.count_nonzero(mask)) * float(pixel_area)


def local_weights_ready(model_dir: Path) -> bool:
    if not model_dir.is_dir():
        return False
    names = {path.name for path in model_dir.iterdir()}
    return bool(names.intersection({"config.json", "model.safetensors", "pytorch_model.bin"}) or list(model_dir.glob("*.pth")))


def predict_windows(stack_hwc: np.ndarray, predict_tile, size: int, overlap: int) -> np.ndarray:
    """Run an injected tile function. `predict_tile` accepts a (tile, bands) array."""
    height, width, _bands = stack_hwc.shape
    pieces = []
    for row, col, tile_h, tile_w in iter_windows(height, width, size, overlap):
        tile = np.zeros((size, size, stack_hwc.shape[2]), dtype=stack_hwc.dtype)
        tile[:tile_h, :tile_w] = stack_hwc[row : row + tile_h, col : col + tile_w]
        prediction = np.asarray(predict_tile(tile))
        pieces.append((row, col, prediction[:tile_h, :tile_w] > 0))
    return stitch_votes(pieces, (height, width))


def write_composite(path: Path, bands: dict[str, np.ndarray], profile: dict) -> None:
    import rasterio

    order = ["B02", "B03", "B04", "B08", "B11", "B12"]
    out_profile = {
        "driver": "GTiff",
        "height": bands["B02"].shape[0],
        "width": bands["B02"].shape[1],
        "count": len(order),
        "dtype": "float32",
        "crs": profile.get("crs"),
        "transform": profile.get("transform"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **out_profile) as dest:
        for index, name in enumerate(order, start=1):
            dest.write(bands[name].astype(np.float32), index)


def try_model_mask(composite: Path, output: Path, settings: Settings) -> np.ndarray | None:
    if not settings.allow_model_download and not local_weights_ready(settings.model_dir):
        return None
    import geoai
    import rasterio

    repo = str(settings.model_dir) if local_weights_ready(settings.model_dir) else settings.model_repo_id
    geoai.timm_segmentation_from_hub(
        input_path=str(composite),
        output_path=str(output),
        repo_id=repo,
        window_size=settings.tile_size,
        overlap=settings.tile_overlap,
        batch_size=1,
    )
    with rasterio.open(output) as source:
        return np.squeeze(source.read(1)) > 0


def segment_bands(bands: dict[str, np.ndarray], valid: np.ndarray, settings: Settings, work_dir: Path, profile: dict) -> dict:
    index_mask = ndwi_mask(bands["B03"], bands["B08"], settings.ndwi_threshold)
    model_mask = None
    if local_weights_ready(settings.model_dir) or settings.allow_model_download:
        composite = work_dir / "composite.tif"
        output = work_dir / "water_mask.tif"
        try:
            write_composite(composite, bands, profile or {})
            model_mask = try_model_mask(composite, output, settings)
        except Exception:
            model_mask = None
    if model_mask is None:
        mask = index_mask & valid
        return {
            "mask": mask,
            "agreement": 1.0,
            "confidence": settings.model_missing_confidence,
            "confidence_reasons": ["segmentation_model_unavailable"],
            "extent_m2": water_extent_m2(mask, settings.pixel_area_m2),
        }
    if model_mask.shape != valid.shape:
        model_mask = model_mask[: valid.shape[0], : valid.shape[1]]
    agreement = agreement_fraction(model_mask, index_mask, valid)
    reasons = []
    confidence = 1.0
    if agreement < settings.agreement_floor:
        confidence = settings.disagreement_confidence
        reasons.append("model_agreement")
    mask = model_mask & valid
    return {
        "mask": mask,
        "agreement": agreement,
        "confidence": confidence,
        "confidence_reasons": reasons,
        "extent_m2": None,
    }
