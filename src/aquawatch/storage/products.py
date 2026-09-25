"""Cached masks and indicator arrays, keyed by the source scene hash."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class ProductStore:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.mask_dir = cache_dir / "masks"
        self.indicator_dir = cache_dir / "indicators"

    def _mask_folder(self, body: str, date: str, scene_hash: str) -> Path:
        return self.mask_dir / body / date / scene_hash

    def _indicator_folder(self, body: str, date: str, scene_hash: str) -> Path:
        return self.indicator_dir / body / date / scene_hash

    def has_mask(self, body: str, date: str, scene_hash: str) -> bool:
        return (self._mask_folder(body, date, scene_hash) / "mask.npy").is_file()

    def save_mask(self, body: str, date: str, scene_hash: str, mask: np.ndarray, meta: dict) -> None:
        folder = self._mask_folder(body, date, scene_hash)
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / "mask.npy", mask)
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    def load_mask(self, body: str, date: str, scene_hash: str) -> np.ndarray | None:
        path = self._mask_folder(body, date, scene_hash) / "mask.npy"
        if not path.is_file():
            return None
        return np.load(path)

    def save_indicators(self, body: str, date: str, scene_hash: str, indicators: dict[str, np.ndarray]) -> None:
        folder = self._indicator_folder(body, date, scene_hash)
        folder.mkdir(parents=True, exist_ok=True)
        for name, array in indicators.items():
            np.save(folder / f"{name}.npy", array)

    def load_indicators(self, body: str, date: str, scene_hash: str, names: list[str]) -> dict[str, np.ndarray] | None:
        folder = self._indicator_folder(body, date, scene_hash)
        loaded = {}
        for name in names:
            path = folder / f"{name}.npy"
            if not path.is_file():
                return None
            loaded[name] = np.load(path)
        return loaded
