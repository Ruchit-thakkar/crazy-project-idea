"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_rgb() -> np.ndarray:
    """64x96 RGB float image, top half bright, bottom half dark."""
    h, w = 64, 96
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[:32, :] = 0.8
    img[32:, :, 0] = 0.1
    img[32:, :, 1] = 0.2
    img[32:, :, 2] = 0.3
    return img


@pytest.fixture
def sample_alpha() -> np.ndarray:
    """Soft circle-ish alpha mask."""
    h, w = 64, 96
    ys, xs = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / (min(w, h) * 0.3)
    alpha = np.clip(1.0 - d, 0.0, 1.0).astype(np.float32)
    return alpha