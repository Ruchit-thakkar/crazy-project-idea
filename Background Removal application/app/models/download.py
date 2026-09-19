"""Model weight downloader.

Fetches the small set of in-house model weights (u2net / u2netp) from
public mirrors. Everything is downloaded once and then the app is fully
offline. Also verifies that a freshly downloaded file is a valid torch
checkpoint before it is used.

Usage:
    python -m app.models.download            # download both models
    python -m app.models.download --names u2net
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

from app.utils.config import models_dir
from app.utils.log import get_logger, setup_logging

log = get_logger("models.download")

_SOURCES = {
    "u2net": [
        # Google Drive (original U-2-Net weights)
        "https://drive.google.com/uc?export=download&id=1ao1ovG1Qtx4b7EoskHXXR2NF9iPeK9Uc",
        # Zenodo/mirror candidates (direct HTTP)
        "https://github.com/MuhammedMelih/Remove-Background-Opencv-and-U2Net/raw/master/u2net.pth",
        "https://github.com/dottedleg/u2net/raw/pytorch-u2net/u2net.pth",
    ],
    "u2netp": [
        "https://drive.google.com/uc?export=download&id=1rbSTGKAE-MTxBYHd-51l2hMOQPT_7Epv",
        "https://github.com/MuhammedMelih/Remove-Background-Opencv-and-U2Net/raw/master/u2netp.pth",
    ],
}

_EXPECTED_SIZES = {
    "u2net": 176_501_756,
    "u2netp": 1_775_690,
}

_EXTRA_NOTE = """
No weight file could be downloaded automatically (common on restricted
networks). Please download manually and place it in the models/ folder:

  u2net  (~168 MB):  https://drive.google.com/file/d/1ao1ovG1Qtx4b7EoskHXXR2NF9iPeK9Uc
                     Mirror 1: https://github.com/MuhammedMelih/Remove-Background-Opencv-and-U2Net/raw/master/u2net.pth

  u2netp (~1.7 MB):  https://drive.google.com/file/d/1rbSTGKAE-MTxBYHd-51l2hMOQPT_7Epv

Save as:  models/u2net.pth   and   models/u2netp.pth

Alternatively install the optional ONNX path (see README) and drop in:
  u2net.onnx  /  modnet.onnx  /  isnet-general-use.onnx
"""


def _drive_confirm(url: str) -> str:
    """Mangle a Google Drive share URL to enable automatic download."""
    if "drive.google.com" not in url:
        return url
    id_ = None
    if "?id=" in url or "&id=" in url:
        for part in url.split("&"):
            if part.strip().startswith("id="):
                id_ = part.split("=", 1)[1]
    elif "/file/d/" in url:
        id_ = url.split("/file/d/")[1].split("/")[0]
    if id_:
        return f"https://drive.google.com/uc?export=download&id={id_}&confirm=t"
    return url


def _download(url: str, dest: Path, timeout: int = 300) -> bool:
    url = _drive_confirm(url)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BGRemove/1.0"},
    )
    chunk = 4 * 1024 * 1024
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as fh:
            while True:
                data = resp.read(chunk)
                if not data:
                    break
                fh.write(data)
        if dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            return False
        return True
    except Exception as exc:
        log.debug("download failed %s: %s", url, exc)
        dest.unlink(missing_ok=True)
        return False


def _validate(name: str, path: Path) -> bool:
    size = path.stat().st_size
    if _EXPECTED_SIZES.get(name) is not None:
        expected = _EXPECTED_SIZES[name]
        tolerance = 0.02 * expected
        if abs(size - expected) > tolerance:
            log.warning(
                "suspicious size for %s: got %d expected %d (±%d)",
                name, size, expected, int(tolerance),
            )
            return False
    try:
        import torch

        sd = torch.load(str(path), map_location="cpu", weights_only=True)
        if not hasattr(sd, "keys") or len(sd) == 0:
            return False
    except Exception as exc:
        log.warning("torch validation failed for %s: %s", name, exc)
        return False
    return True


def ensure_u2net_weights(
    folder: str | Path,
    names: list[str] | None = None,
) -> dict[str, bool]:
    """Try to ensure the requested weights exist; return status map.

    Only downloads when missing. Never blocks a run for long.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    names = names or ["u2net", "u2netp"]
    status: dict[str, bool] = {}
    for name in names:
        target = folder / f"{name}.pth"
        if target.exists() and target.stat().st_size > 0:
            status[name] = True
            continue
        log.info("weight '%s' missing — attempting download...", name)
        ok = False
        for url in _SOURCES.get(name, []):
            log.info("  trying %s", url)
            if _download(url, target):
                if _validate(name, target):
                    ok = True
                    break
                log.warning("  downloaded file failed validation, retrying next mirror")
        status[name] = ok
        if ok:
            log.info("  ok: %s (%d bytes)", target.name, target.stat().st_size)
        else:
            log.warning("  could not download %s", name)
    return status


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download U2-Net weights (offline afterwards)")
    parser.add_argument("--names", nargs="*", default=["u2net", "u2netp"])
    parser.add_argument("--folder", default=str(models_dir()))
    args = parser.parse_args()

    setup_logging()
    outcome = ensure_u2net_weights(args.folder, args.names)
    ok = all(outcome.values())
    if not ok:
        print(_EXTRA_NOTE)
        return 1
    print("\nAll requested model weights are ready. The app is now fully offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())