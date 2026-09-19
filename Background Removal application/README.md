# AI Background Removal Application

A fully local, professional background-removal desktop app for Windows.

**The core rule of this project: remove the background, never the image quality.**

The extracted image keeps its **original pixels at the original resolution**
and is exported as a **lossless transparent PNG** (8-bit or 16-bit, matching the
source). Nothing is re-encoded to JPEG, downscaled, or recompressed.

## Features

- **Drop-zone UI** — drag & drop an image (PNG, JPEG, TIFF, WebP, BMP) or use the file picker.
- **One-click removal** — model preset selection, automatic CPU/GPU/MPS device detection.
- **Presets** — `Auto`, `Fast`, `High Quality`, `Human`, `Product`, `Hair/Fur`.
- **Quality levels** — `Ultra Quality`, `High Quality`, `Standard`.
- **Alpha matting** — sampling-based matting with trimap + nearest-seed EDT; soft hair/fur edges without halos.
- **Edge refinement** — guided filter, speckle removal, defringe, edge cleaning.
- **Manual refinement** — paint strokes to add foreground, remove, or restore; refine edge; brush size slider; undo/redo.
- **Background replacement** — Transparent, White, Black, Custom Color, Custom Image, Blurred Background, Checkerboard.
- **Batch processing** — process whole folders, Pause / Resume / Cancel, retry failures, custom output prefix/format.
- **Export verification** — every export is reopened and byte-compared at the pixel level before it is considered saved.
- **Huge-image safety** — tiled processing with seam feathering keeps memory bounded; oversized sources are refused with clear errors.

## Install

Requires **Python 3.10+** (3.13 recommended). Works on Windows (and on Linux/macOS with CUDA/MPS for acceleration).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

`requirements.txt` installs:

| Package | Purpose |
| --- | --- |
| torch   | main inference engine (U<sub>2</sub>-Net). CPU-only wheel is fine; install CUDA wheels from pytorch.org for GPU. |
| numpy, scipy, Pillow | image math + quality-preserving processing |
| PySide6 | GUI |

Optional extras (commented in `requirements.txt`): `onnxruntime` (ONNX models
below) and `rembg` (advanced backup engine).

## Download the AI model weights

The `u2net` (~168 MB) and `u2netp` (~1.7 MB) weights are not bundled. Fetch them:

```powershell
python -m app.models.download
```

or download manually into `models/`:
- `models/u2net.pth` — https://drive.google.com/file/d/1ao1ovG1Qtx4b7EoskHXXR2NF9iPeK9Uc
- `models/u2netp.pth` — https://drive.google.com/file/d/1rbSTGKAE-MTxBYHd-51l2hMOQPT_7Epv

After download, verified weight compatibility before the model is used.

### Optional ONNX engines

Drop any of these into `models/` for additional engine choices:
- `modnet.onnx`
- `isnet-general-use.onnx`
- `u2net.onnx`

Requires `pip install onnxruntime`. These allow proven exported IS-Net / MODNet
models to be used without maintaining their architectures in this codebase.

## Run

```powershell
python main.py
```

## GUI walkthrough

1. Drop an image onto the window.
2. Choose **Preset**, **Quality**, and click **Remove Background**.
3. Inspect the result in the **Compare** tab (before/after divider).
4. Refine with the mask brushes and **Undo** until every edge is right.
5. Set a **Background** mode, or keep **Transparent**.
6. **Export PNG** — the file is written losslessly, then re-opened and verified.

The **Batch** button opens the folder-processing dialog (pause/resume/cancel,
worker count, output naming, overwrite policy, retry).

## Quality guarantees (enforced in code)

- **No downscaling of the exported image.** Inference may run at model
  resolution internally, but the final alpha is resampled back to the original
  dimensions and composited with the *original* pixels.
- **Lossless PNG only.** 8-bit sources export 8-bit PNG; 16-bit sources export
  true 16-bit RGBA PNG via a built-in lossless encoder.
- **No EXIF loss for stills.** Orientation is honored on input and the exported
  DPI/metadata are preserved.
- **Verification before success.** `verify_file` re-opens the saved output and
  compares every pixel; failures are reported rather than silently accepted.

## Architecture

| Module | Responsibility |
| --- | --- |
| `app/image/loader.py` | decode + EXIF orientation + bit-depth detection |
| `app/image/io.py` | lossless PNG (8/16-bit) + TIFF export |
| `app/image/tiles.py` | tiled processing with seam feathering |
| `app/models/u2net.py` | U<sub>2</sub>-Net / U<sub>2</sub>-NetP torch architecture |
| `app/models/registry.py` | preset → engine resolution + preprocessing |
| `app/models/onnx_engine.py` | optional ONNX Runtime engines |
| `app/models/download.py` | weight download + validation |
| `app/segmentation/engine.py` | multi-scale/ensemble segmentation |
| `app/matting/matting.py` | trimap matting (nearest-seed sampling EDT) |
| `app/processing/refine.py` | guided filter, defringe, edge cleaning |
| `app/processing/pipeline.py` | full pipeline orchestration |
| `app/processing/background.py` | background replacement modes |
| `app/processing/verify.py` | export verification |
| `app/batch/worker.py` | batch processing (pause/resume/cancel) |
| `app/ui/` | PySide6 GUI (main window, compare view, batch dialog, workers) |

## Build a standalone `.exe`

```powershell
pip install pyinstaller
python build.py
```

The build collects the app, model downloader, and required binaries into
`dist/`.

## Tests

```powershell
python -m pytest tests -q
```

Tests cover lossless export (8/16-bit), the alpha/matting pipeline, image info,
pipeline composition, and batch handling. Torch-dependent tests auto-skip when
torch is not installed.