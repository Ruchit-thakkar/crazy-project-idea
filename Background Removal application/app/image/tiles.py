"""Tiled processing for extremely large images.

Instead of permanently downscaling huge inputs, heavy per-pixel stages
(edge refinement / matting / filtering) can operate tile-bat-tile so memory
stays bounded.  Tiles overlap so seams never become visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.utils.log import get_logger

log = get_logger("image.tiles")


@dataclass
class Tile:
    x0: int
    y0: int
    x1: int
    y1: int


def build_tiles(
    height: int,
    width: int,
    tile_size: int = 1024,
    overlap: int = 64,
) -> list[Tile]:
    """Partition an image into overlapping tiles."""
    if tile_size <= 0:
        return [Tile(0, 0, width, height)]
    overlap = max(0, min(overlap, tile_size // 2))
    stride = tile_size - overlap
    tiles: list[Tile] = []
    y = 0
    while y < height:
        x = 0
        while x < width:
            x1 = min(x + tile_size, width)
            y1 = min(y + tile_size, height)
            tiles.append(Tile(x, y, x1, y1))
            if x1 >= width:
                break
            x += stride
        if y1 >= height:
            break
        y += stride
    return tiles


def process_tiled_multi(
    arrays: list[np.ndarray],
    fn: Callable[[list[np.ndarray]], list[np.ndarray]],
    tile_size: int = 1024,
    overlap: int = 64,
    channel_axis: int = 2,
) -> list[np.ndarray]:
    """Apply `fn(tile_slices) -> list[tile_outputs]` per tile and blend seams.

    All arrays in `arrays` must share the same spatial size. The function
    receives the same spatial window from each array and may return one or
    more same-size outputs, which are stitched back with linear feathering
    across the overlap region.
    """
    if not arrays:
        return []
    shape = arrays[0].shape
    height, width = shape[:2]

    outputs = [np.zeros_like(a, dtype=np.float32) for a in arrays]
    weights = [np.zeros(shape[:2], dtype=np.float32) for _ in arrays]

    for tile in build_tiles(height, width, tile_size, overlap):
        x0, y0, x1, y1 = tile.x0, tile.y0, tile.x1, tile.y1
        slices = [a[y0:y1, x0:x1] if a.ndim == channel_axis + 1 else a[y0:y1, x0:x1] for a in arrays]
        results = fn(slices)

        ones = np.ones((y1 - y0, x1 - x0), dtype=np.float32)
        feather = ones.copy()
        if overlap > 0 and (y1 - y0 > overlap) and (x1 - x0 > overlap):
            ramp = np.linspace(0.0, 1.0, min(overlap, (y1 - y0) // 2))
        else:
            ramp = None
        if ramp is not None:
            feather[: ramp.size, :] *= ramp[:, None]
            feather[-ramp.size:, :] *= ramp[::-1][:, None]
            feather[:, : ramp.size] *= ramp[None, :]
            feather[:, -ramp.size:] *= ramp[::-1][None, :]
        # A floor keeps border pixels from collapsing to weight 0 and losing
        # their data during normalization (double coverage fixes the interior).
        feather = np.maximum(feather, 0.02)

        for idx, res in enumerate(results):
            if res.ndim == channel_axis + 1:
                outputs[idx][y0:y1, x0:x1] += res * feather[..., None]
                weights[idx][y0:y1, x0:x1] += feather
            else:
                outputs[idx][y0:y1, x0:x1] += res * feather
                weights[idx][y0:y1, x0:x1] += feather

    final = []
    for idx, arr in enumerate(outputs):
        w = np.maximum(weights[idx], 1e-6)
        if arr.ndim == channel_axis + 1:
            final.append(arr / w[..., None])
        else:
            final.append(arr / w)
    return final


def megapixels_of(size: tuple[int, int]) -> float:
    return (size[0] * size[1]) / 1_000_000.0