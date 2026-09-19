"""Batch robustness tests: one corrupt file must not break the batch."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.batch.worker import BatchSettings, discover_images, process_one


def test_discover_images_recursive(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "x.jpg").write_bytes(b"junk")
    (tmp_path / "a" / "b" / "y.png").write_bytes(b"junk")
    (tmp_path / "a" / "z.txt").write_text("no", encoding="utf-8")
    found = discover_images(tmp_path)
    names = sorted(p.name for p in found)
    assert names == ["x.jpg", "y.png"]


def test_process_one_handles_corrupt(tmp_path):
    good = tmp_path / "good.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(good, format="PNG")
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")

    out_dir = tmp_path / "out"
    task_good = {
        "input": str(good), "output": str(out_dir / "good.png"),
        "models_folder": str(tmp_path / "nonexistent_models"),
        "preset": "Auto", "quality": "Ultra Quality",
        "max_inference_side": 320, "background_mode": "Transparent",
        "background_color": [1.0, 1.0, 1.0], "blur_radius": 16.0,
        "preserve_metadata": True, "overwrite": False,
    }
    task_bad = dict(task_good)
    task_bad["input"] = str(bad)
    task_bad["output"] = str(out_dir / "bad.png")

    r_bad = process_one(task_bad)
    assert r_bad.status == "failed"
    assert r_bad.error  # informative error

    # Even with missing model weights the corrupt file fails cleanly,
    # and the framework keeps going for other files (documented behaviour).
    r_good = process_one(task_good)
    assert r_good.status in ("ok", "failed")