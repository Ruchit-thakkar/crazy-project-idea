"""Quality-core tests: lossless IO, dimensions, alpha, metadata round-trip."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.image.io import assemble_rgba, export_transparent_png, save_png
from app.image.loader import load
from app.metadata.bundle import MetadataBundle
from app.processing.verify import verify_file, verify_floats


def test_assemble_rgba_8bit_exact(tmp_path):
    rgb = np.random.default_rng(0).random((7, 9, 3), dtype=np.float32)
    alpha = np.random.default_rng(1).random((7, 9), dtype=np.float32)
    img = assemble_rgba(rgb, alpha.copy(), bit_depth=8)
    assert img.mode == "RGBA"
    arr = np.asarray(img)
    expect_rgb = (rgb * 255 + 0.5).astype(np.uint8)
    expect_a = (alpha * 255 + 0.5).astype(np.uint8)
    assert np.array_equal(arr[..., :3], expect_rgb)
    assert np.array_equal(arr[..., 3], expect_a)


def test_save_rgba16_png_lossless(tmp_path):
    import zlib
    from pathlib import Path

    from app.image.io import save_rgba16_png

    rng = np.random.default_rng(2)
    rgb = rng.integers(0, 65536, size=(5, 6, 3)).astype(np.uint16)
    a = rng.integers(0, 65536, size=(5, 6)).astype(np.uint16)
    out = tmp_path / "deep.png"
    save_rgba16_png(out, rgb, a, dpi=(300, 300))

    data = Path(out).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR must declare 16-bit RGBA (bit depth 16, color type 6)
    ihdr = data[16:29]
    assert ihdr[8] == 16 and ihdr[9] == 6

    # decode IDAT manually and verify exact round-trip
    import struct

    off = 8
    idat = b""
    while off < len(data):
        (length,) = struct.unpack(">I", data[off:off + 4])
        tag = data[off + 4:off + 8]
        chunk = data[off + 8:off + 8 + length]
        if tag == b"IDAT":
            idat += chunk
        off += 12 + length

    raw = zlib.decompress(idat)
    h, w = rgb.shape[:2]
    assert len(raw) == h * (w * 8 + 1)
    # reconstruct channel 0 / alpha (1 filter byte per scanline)
    rows = np.frombuffer(raw, dtype=np.uint8).reshape(h, w * 8 + 1)[:, 1:].copy()
    R = (rows[:, 0::8].astype(np.uint16) << 8) | rows[:, 1::8].astype(np.uint16)
    A = (rows[:, 6::8].astype(np.uint16) << 8) | rows[:, 7::8].astype(np.uint16)
    assert np.array_equal(R, rgb[..., 0])
    assert np.array_equal(A, a)


def test_export_png_dimensions_and_lossless(tmp_path):
    rgb = np.full((20, 30, 3), 0.5, dtype=np.float32)
    alpha = np.ones((20, 30), dtype=np.float32)
    alpha[5:15, 5:25] = 0.25
    out = tmp_path / "out.png"
    export_transparent_png(rgb, alpha, out)
    with Image.open(out) as im:
        assert im.size == (30, 20)
        assert im.mode == "RGBA"
    arr = np.asarray(Image.open(out).convert("RGBA"))
    assert (arr[..., 3] == (alpha * 255 + 0.5).astype(np.uint8)).all()
    assert (arr[..., :3] == (rgb * 255 + 0.5).astype(np.uint8)).all()


def test_png_never_recompresses(tmp_path):
    """Round-tripping a PNG must preserve every pixel exactly."""
    rng = np.random.default_rng(3)
    path = tmp_path / "src.png"
    Image.fromarray(rng.integers(0, 256, (12, 14, 3), dtype=np.uint8)).save(path, format="PNG")

    loaded = load(path)
    assert np.asarray(loaded.rgb).dtype == np.float32

    alpha = np.ones((12, 14), dtype=np.float32) * 0.9
    out = tmp_path / "dst.png"
    export_transparent_png(loaded.rgb, alpha, out)
    with Image.open(out) as im:
        assert im.size == (14, 12)
        r1, g1, b1 = im.convert("RGB").split()
    with Image.open(path) as im:
        r0, g0, b0 = im.convert("RGB").split()
    assert r0.tobytes() == r1.tobytes()
    assert g0.tobytes() == g1.tobytes()
    assert b0.tobytes() == b1.tobytes()


def test_verify_floats():
    rgb = np.zeros((10, 8, 3), dtype=np.float32)
    alpha = np.ones((10, 8), dtype=np.float32)
    ok = verify_floats((8, 10), rgb, alpha)
    assert ok.passed
    bad = verify_floats((9, 10), rgb, alpha)
    assert not bad.passed


def test_verify_file(tmp_path):
    rgb = np.zeros((5, 6, 3), dtype=np.float32)
    alpha = np.ones((5, 6), dtype=np.float32)
    p = tmp_path / "test.png"
    export_transparent_png(rgb, alpha, p)
    assert verify_file((6, 5), p).passed
    # wrong expected size -> fail
    assert not verify_file((7, 5), p).passed


def test_metadata_bundle_roundtrip(tmp_path):
    src = tmp_path / "src.jpg"
    im = Image.new("RGB", (20, 20), (200, 100, 50))
    exif = Image.Exif()
    from PIL.ExifTags import Base
    exif[Base.Orientation] = 1
    im.save(src, format="JPEG", exif=exif, dpi=(300, 300))

    bundle = MetadataBundle.from_image_path(src)
    assert bundle.dpi is not None
    assert bundle.dpi[0] == 300

    rgb = np.zeros((20, 20, 3), dtype=np.float32)
    a = np.ones((20, 20), dtype=np.float32)
    out = tmp_path / "out.png"
    export_transparent_png(rgb, a, out, metadata=bundle, preserve_metadata=True)
    with Image.open(out) as img:
        if img.getexif():
            assert img.getexif().get(274, 1) == 1
        assert img.info.get("dpi", (0, 0))[0] == pytest.approx(300, abs=1.0)