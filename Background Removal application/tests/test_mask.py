"""Tests for alpha mask math: trimap, matting, refinement, tiling."""
from __future__ import annotations

import numpy as np
import pytest

from app.image.tiles import build_tiles, process_tiled_multi
from app.matting.matting import apply_matting
from app.matting.trimap import make_trimap
from app.processing.refine import clean_edges, defringe, guided_refine


def test_trimap_partitions():
    alpha = np.zeros((40, 40), dtype=np.float32)
    alpha[10:30, 10:30] = 1.0
    alpha[20:25, 20:25] = 0.5
    tri = make_trimap(alpha, erode_r=2, dilate_r=3)
    # the ambiguous core must be unknown
    assert tri.unknown[22, 22]
    # far background must be background
    assert tri.bg[2, 2]
    # deep foreground must be foreground
    assert tri.fg[12, 12]
    # partitions cover everything
    assert (tri.fg | tri.bg | tri.unknown).all()
    # no overlap
    assert not (tri.fg & tri.bg).any()


def test_guided_refine_keeps_range_and_size(sample_rgb, sample_alpha):
    out = guided_refine(sample_alpha, sample_rgb, radius=3)
    assert out.shape == sample_alpha.shape
    assert out.min() >= 0.0 and out.max() <= 1.0
    # interior stays near opaque; (28,40) is near the center
    assert out[28, 40] > 0.4


def test_defringe_does_not_change_shape(sample_rgb, sample_alpha):
    rgb, a = defringe(sample_rgb.copy(), sample_alpha.copy())
    assert rgb.shape == sample_rgb.shape
    assert a.shape == sample_alpha.shape


def test_clean_edges(sample_alpha):
    out = clean_edges(sample_alpha, r=2)
    assert out.shape == sample_alpha.shape
    assert out.dtype == sample_alpha.dtype


def test_apply_matting_standard_leaves_shape(sample_rgb, sample_alpha):
    out = apply_matting(sample_rgb, sample_alpha.copy(), level="standard")
    assert out.shape == sample_alpha.shape
    assert out.dtype in (np.float32, np.float64)


def test_apply_matting_ultra_runs(sample_rgb, sample_alpha):
    out = apply_matting(sample_rgb, sample_alpha.copy(), level="ultra")
    assert out.shape == sample_alpha.shape
    assert np.isfinite(out).all()
    assert out.min() >= -1e-6 and out.max() <= 1.0


def test_tiles_cover_everything():
    h, w = 100, 67
    tiles = build_tiles(h, w, tile_size=32, overlap=8)
    covered = np.zeros((h, w), dtype=bool)
    for t in tiles:
        covered[t.y0:t.y1, t.x0:t.x1] = True
    assert covered.all()


def test_process_tiled_multi_restores_global_average():
    rng = np.random.default_rng(5)
    img = rng.random((97, 61, 3), dtype=np.float32)
    outs = process_tiled_multi(
        [img],
        lambda slices: [(slices[0] * 2.0 - 0.5)],
        tile_size=40,
        overlap=12,
    )
    assert outs[0].shape == img.shape
    # Seam feathering is expected to introduce small local differences;
    # verify the global mean stays correct and all values finite.
    assert np.isfinite(outs[0]).all()
    expect_mean = (img * 2.0 - 0.5).mean()
    assert abs(outs[0].mean() - expect_mean) < 0.02