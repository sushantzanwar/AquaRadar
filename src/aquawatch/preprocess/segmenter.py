"""Local UNet++ / EfficientNet-B4 water model. Weights are loaded once per process."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from aquawatch.geo.tiles import iter_windows, stitch_votes

REPO_ID = "giswqs/s2-water-unetplusplus-efficientnet-b4"
MODEL_BANDS = ("B2", "B3", "B4", "B8", "B11", "B12")
TILE = 512
OVERLAP = 256
_CACHE: dict[str, object] = {}


class WeightsNotFound(FileNotFoundError):
    pass


def find_weights(model_dir: Path) -> Path:
    if not model_dir.is_dir():
        raise WeightsNotFound(f"model directory missing: {model_dir}")
    preferred = (
        "model.safetensors",
        "pytorch_model.bin",
        "model.pth",
        "weights.pth",
        "best_model.pth",
    )
    for name in preferred:
        path = model_dir / name
        if path.is_file():
            return path
    found = sorted(model_dir.glob("*.safetensors")) + sorted(model_dir.glob("*.bin")) + sorted(model_dir.glob("*.pth"))
    if not found:
        raise WeightsNotFound(
            f"no local weights in {model_dir}. Download {REPO_ID} before preprocessing; this step does not contact Hugging Face."
        )
    return found[0]


def scale_reflectance(image: np.ndarray) -> np.ndarray:
    """Map L2A digital numbers to reflectance when the scene is still scaled by 10000."""
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return np.zeros_like(image, dtype=np.float32)
    if float(np.nanpercentile(finite, 99)) > 2:
        return (image / 10000.0).astype(np.float32)
    return image.astype(np.float32)


def load_model(model_dir: Path):
    """Build UnetPlusPlus-EfficientNet-B4 and cache it for the process."""
    key = str(model_dir.resolve())
    if key in _CACHE:
        return _CACHE[key]
    import segmentation_models_pytorch as smp
    import torch

    weights = find_weights(model_dir)
    model = smp.UnetPlusPlus(
        encoder_name="efficientnet-b4",
        encoder_weights=None,
        in_channels=6,
        classes=2,
    )
    state = _read_state(weights)
    model.load_state_dict(state, strict=False)
    model.eval()
    _CACHE[key] = (model, torch)
    return _CACHE[key]


def predict_water(image_6hw: np.ndarray, model_dir: Path) -> np.ndarray:
    model, torch = load_model(model_dir)
    scaled = scale_reflectance(np.nan_to_num(image_6hw, nan=0.0).astype(np.float32))
    _, height, width = scaled.shape
    pieces = []
    for row, col, tile_h, tile_w in iter_windows(height, width, TILE, OVERLAP):
        tile = np.zeros((6, TILE, TILE), dtype=np.float32)
        tile[:, :tile_h, :tile_w] = scaled[:, row : row + tile_h, col : col + tile_w]
        tensor = torch.from_numpy(tile).unsqueeze(0)
        with torch.no_grad():
            logits = model(tensor)
        if isinstance(logits, (tuple, list)):
            logits = logits[0]
        classes = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy()
        pieces.append((row, col, (classes[:tile_h, :tile_w] == 1).astype(np.float32)))
    return stitch_votes(pieces, (height, width))


def _read_state(path: Path) -> dict:
    if path.suffix == ".safetensors":
        from safetensors.torch import load_file

        blob = load_file(str(path))
    else:
        import torch

        blob = torch.load(path, map_location="cpu", weights_only=False)
        if isinstance(blob, dict) and "state_dict" in blob:
            blob = blob["state_dict"]
    cleaned = {}
    for key, value in blob.items():
        name = key
        for prefix in ("model.", "module.", "net."):
            if name.startswith(prefix):
                name = name[len(prefix) :]
        cleaned[name] = value
    return cleaned
