"""Tests for image detection and loading behaviour."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.image import info as img_info
from app.image.loader import load, mode_to_16bit


def _save(path, im):
    im.save(path)
    return path


def test_analyze_detects_png(tmp_path):
    p = tmp_path / "sample.png"
    Image.new("RGB", (40, 25), (10, 20, 30)).save(p)
    info = img_info.analyze(p)
    assert info.format == "PNG"
    assert info.width == 40 and info.height == 25
    assert info.effective_size == (40, 25)
    assert info.color_mode == "8-bit RGB"
    assert info.bit_depth == 8


def test_analyze_orientation_swaps(tmp_path):
    p = tmp_path / "rot.jpg"
    im = Image.new("RGB", (10, 60), (10, 20, 30))
    exif = Image.Exif()
    from PIL.ExifTags import Base
    exif[Base.Orientation] = 6  # 90° CW
    im.save(p, format="JPEG", exif=exif)
    info = img_info.analyze(p)
    assert info.orientation == 6
    assert info.effective_size == (60, 10)


def test_unsupported_raises(tmp_path):
    p = tmp_path / "x.gif"
    Image.new("RGB", (4, 4), (0, 0, 0)).save(p, format="GIF")
    with pytest.raises(img_info.UnsupportedImageError):
        img_info.analyze(p)


def test_corrupt_raises(tmp_path):
    p = tmp_path / "bad.png"
    p.write_bytes(b"not a real image at all")
    with pytest.raises(img_info.CorruptImageError):
        img_info.analyze(p)


def test_loader_exif_orientation_applied(tmp_path):
    p = tmp_path / "exif.jpg"
    im = Image.new("RGB", (10, 60), (5, 8, 12))
    exif = Image.Exif()
    from PIL.ExifTags import Base
    exif[Base.Orientation] = 6
    im.save(p, format="JPEG", exif=exif)
    loaded = load(p)
    h, w = loaded.rgb.shape[:2]
    assert (w, h) == (60, 10)
    assert loaded.info.effective_size == (60, 10)


def test_loader_preserves_rgb(tmp_path):
    rng = np.random.default_rng(9)
    rgb8 = rng.integers(0, 256, (24, 31, 3), dtype=np.uint8)
    p = tmp_path / "src.png"
    Image.fromarray(rgb8).save(p, format="PNG")
    loaded = load(p)
    back = np.clip(loaded.rgb * 255 + 0.5, 0, 255).astype(np.uint8)
    assert np.array_equal(back, rgb8)


def test_loader_16bit(tmp_path):
    p = tmp_path / "gray16.png"
    arr = np.arange(256, dtype=np.uint16).reshape(16, 16) * 256
    Image.fromarray(arr, mode="I;16").save(p)
    loaded = load(p)
    assert mode_to_16bit(loaded.source_mode) is True
    assert loaded.bit_depth == 16