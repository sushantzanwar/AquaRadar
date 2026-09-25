"""512×512 windows for the six-band water model, and overlap stitching."""

from __future__ import annotations

import numpy as np


def iter_windows(height: int, width: int, size: int = 512, overlap: int = 256):
    if size < 1:
        raise ValueError("tile size must be positive")
    step = max(size - overlap, 1)
    rows = list(range(0, max(height - size, 0) + 1, step)) or [0]
    cols = list(range(0, max(width - size, 0) + 1, step)) or [0]
    if rows[-1] != max(height - size, 0):
        rows.append(max(height - size, 0))
    if cols[-1] != max(width - size, 0):
        cols.append(max(width - size, 0))
    for row in rows:
        for col in cols:
            yield row, col, min(size, height - row), min(size, width - col)


def stitch_votes(pieces: list[tuple[int, int, np.ndarray]], shape: tuple[int, int]) -> np.ndarray:
    """Average overlapping binary tiles and threshold at 0.5."""
    total = np.zeros(shape, dtype=np.float32)
    votes = np.zeros(shape, dtype=np.float32)
    for row, col, tile in pieces:
        tile = np.asarray(tile, dtype=np.float32)
        height, width = tile.shape
        total[row : row + height, col : col + width] += tile
        votes[row : row + height, col : col + width] += 1
    average = np.divide(total, votes, out=np.zeros_like(total), where=votes > 0)
    return average >= 0.5
