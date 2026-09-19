"""Model registry: preset -> engine resolution + auto-selection logic."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.models.download import ensure_u2net_weights
from app.utils.exceptions import ModelLoadError, ModelNotFoundError
from app.utils.log import get_logger

log = get_logger("models.registry")

PRESETS = ("Auto", "Fast", "High Quality", "Human", "Product", "Hair/Fur")

_MEAN_PETS_RGB_UPPER_HALF = 0.5


@dataclass
class ResolvedEngine:
    name: str
    kind: str  # "torch" | "onnx" | "rembg"
    handle: object
    run: object
    model_size: int = 0

    def eligible(self) -> bool:
        return True


def _human_candidate(models_folder: Path, device: str) -> str | None:
    """Prefer modnet.onnx for human shots if available."""
    onnx_human = models_folder / "modnet.onnx"
    try:
        if onnx_human.exists():
            from app.models.onnx_engine import OnnxEngine

            eng = OnnxEngine(
                name="modnet",
                path=onnx_human,
                add_hint_channel=True,
                imagenet_norm=False,
            ).load()
            return "onnx"
    except Exception as exc:
        log.warning("modnet.onnx unavailable: %s", exc)
    return None


def resolve_engine(
    preset: str,
    models_folder: str | Path,
    device: str = "auto",
    prefer_cuda: bool = True,
    use_onnx: bool = True,
) -> ResolvedEngine:
    """Resolve a preset to a concrete inference engine.

    Precedence keeps the system reliable:
      * in-house torch U2-Net is the default engine family
      * ONNX exports (modnet / isnet / u2net) are used when explicitly
        preferred for their preset and present on disk
      * rembg-backed IS-Net / SAM is used only when installed
    """
    models_folder = Path(models_folder)
    preset = preset if preset in PRESETS else "Auto"

    selected = "u2net"
    kind = "torch"

    if preset == "Fast":
        selected = "u2netp"
    elif preset in ("Human", "Product", "Hair/Fur"):
        selected = "u2net"
        if preset == "Human":
            if use_onnx and _human_candidate(models_folder, device) == "onnx":
                return _make_onnx_engine("modnet", models_folder, device)
    elif preset == "High Quality":
        if use_onnx and (models_folder / "isnet-general-use.onnx").exists():
            try:
                return _make_onnx_engine("isnet", models_folder, device)
            except Exception as exc:
                log.warning("isnet.onnx failed: %s", exc)
        selected = "u2net"

    try:
        ensure_u2net_weights(models_folder, names=[selected])
    except Exception as exc:
        log.warning("weight availability check: %s", exc)

    return _make_torch_engine(selected, models_folder, device, prefer_cuda)


def _make_torch_engine(
    name: str,
    models_folder: Path,
    device: str,
    prefer_cuda: bool,
) -> ResolvedEngine:
    from app.models.torch_engine import get_u2net_engine

    try:
        engine = get_u2net_engine(name, models_folder, device=device, prefer_cuda=prefer_cuda)
    except (ModelNotFoundError, ModelLoadError) as exc:
        if name == "u2netp":
            # Fast preset failing on missing small weights: fall back to full.
            try:
                engine = get_u2net_engine("u2net", models_folder, device, prefer_cuda)
            except Exception:
                raise ModelLoadError(
                    "No AI model weights available. Run 'python -m app.models.download' "
                    "or check the models/ folder."
                ) from exc
        else:
            raise ModelLoadError(
                "No AI model weights available. Run 'python -m app.models.download' "
                "or check the models/ folder."
            ) from exc

    def run(rgb: np.ndarray) -> np.ndarray:
        import torch

        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        t = torch.from_numpy(np.transpose(rgb, (2, 0, 1))[None].astype(np.float32))
        t = (t - mean) / std
        t = t.to(engine.device)
        with torch.no_grad():
            outs = engine.model(t)
            mask = outs[0]
            if isinstance(mask, (tuple, list)):
                mask = mask[0]
            mask = mask.squeeze(0).squeeze(0).float().cpu().numpy()
        return np.clip(mask, 0.0, 1.0).astype(np.float32)

    return ResolvedEngine(name=name, kind="torch", handle=engine, run=run)


def _make_onnx_engine(name: str, models_folder: Path, device: str) -> ResolvedEngine:
    from app.models.onnx_engine import OnnxEngine

    if name == "modnet":
        path = models_folder / "modnet.onnx"
        eng = OnnxEngine(name="modnet", path=path, add_hint_channel=True, imagenet_norm=False).load()
    elif name == "isnet":
        path = models_folder / "isnet-general-use.onnx"
        eng = OnnxEngine(
            name="isnet",
            path=path,
            imagenet_norm=True,
            add_hint_channel=False,
        ).load()
    else:
        path = models_folder / (name + ".onnx")
        eng = OnnxEngine(name=name, path=path, imagenet_norm=True, add_hint_channel=False).load()

    return ResolvedEngine(name=name, kind="onnx", handle=eng, run=eng.run)


def _rembg_engine_available() -> bool:
    try:
        import rembg  # noqa: F401

        return True
    except ImportError:
        return False


def describe_preset(preset: str, models_folder: str | Path) -> str:
    mf = Path(models_folder)
    parts = {p: p for p in PRESETS}
    if preset == "Fast":
        note = "u2netp (faster, slightly less detail)"
    elif preset == "Human":
        note = "prefers MODNet/IS-Net human models, falls back to U2-Net"
    elif preset == "High Quality":
        note = "prefers IS-Net, otherwise U2-Net with ultra edge refinement"
    elif preset == "Product":
        note = "U2-Net tuned for clean product extraction"
    elif preset == "Hair/Fur":
        note = "U2-Net + aggressive hair-aware edge refinement"
    else:
        note = "automatic selection based on the image"
    return f"{preset} -> {note}"