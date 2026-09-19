"""Tests for background composition and the AI model pipeline."""
from __future__ import annotations

import numpy as np
import pytest

from app.processing.background import BLACK, TRANSPARENT, WHITE, compose


def test_transparent_keeps_alpha():
    rgb = np.random.default_rng(0).random((8, 8, 3)).astype(np.float32)
    a = np.pad(np.zeros((6, 6)), ((1, 1), (1, 1)), constant_values=1).astype(np.float32)
    out_rgb, out_a = compose(rgb, a, mode=TRANSPARENT)
    assert np.array_equal(out_rgb, rgb)
    assert np.array_equal(out_a, a)


def test_white_background_fills():
    rgb = np.zeros((10, 10, 3), dtype=np.float32)
    a = np.zeros((10, 10), dtype=np.float32)
    a[2:8, 2:8] = 1.0
    out_rgb, out_a = compose(rgb, a, mode=WHITE)
    assert (out_a == 1.0).all()
    assert np.allclose(out_rgb[0, 0], [1.0, 1.0, 1.0])
    assert np.allclose(out_rgb[5, 5], [0.0, 0.0, 0.0])


def test_custom_color():
    rgb = np.zeros((6, 6, 3), dtype=np.float32)
    a = np.ones((6, 6), dtype=np.float32) * 0.0
    out_rgb, _ = compose(rgb, a, mode="Custom Color", color=(0.3, 0.6, 0.9))
    assert np.allclose(out_rgb[0, 0], (0.3, 0.6, 0.9))


def test_black():
    rgb = np.ones((5, 5, 3), dtype=np.float32)
    a = np.zeros((5, 5), dtype=np.float32)
    a[1:4, 1:4] = 1.0
    out_rgb, _ = compose(rgb, a, mode=BLACK)
    assert np.allclose(out_rgb[0, 0], (0, 0, 0))
    assert np.allclose(out_rgb[2, 2], (1, 1, 1))


def test_custom_image_resized():
    rgb = np.zeros((10, 20, 3), dtype=np.float32)
    a = np.zeros((10, 20), dtype=np.float32)
    bg = np.ones((3, 3, 3), dtype=np.float32) * 0.7
    out_rgb, _ = compose(rgb, a, mode="Custom Image", background_image=bg)
    assert out_rgb.shape == (10, 20, 3)
    assert np.allclose(out_rgb[0, 0], 0.7, atol=0.01)


def test_blurred_background():
    rgb = np.random.default_rng(1).random((12, 12, 3)).astype(np.float32)
    a = np.zeros((12, 12), dtype=np.float32)
    a[3:9, 3:9] = 1.0
    out_rgb, out_a = compose(rgb, a, mode="Blurred Background", blur_radius=8.0)
    assert out_rgb.shape == rgb.shape
    assert (out_a == 1.0).all()


def test_pipeline_smoke_runs_if_torch_available():
    torch = pytest.importorskip("torch", reason="torch not installed")
    from pathlib import Path

    from app.models.register_arch import build_u2net_smoke_check
    from app.utils.config import models_dir

    # Only architectural verification without weights — no download during tests.
    model_ok = build_u2net_smoke_check(torch)
    assert model_ok, "u2net architecture must produce finite output"