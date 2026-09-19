"""High-level segmentation engine.

Runs a resolved AI engine per image, choosing the largest sensible inference
resolution and optionally fusing multiple passes. The resulting soft mask is
always brought back to the original image resolution.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.models.registry import ResolvedEngine, resolve_engine
from app.utils.log import get_logger

log = get_logger("segmentation.engine")

_MAX_INFERENCE_SIDE = 1536
_PIL_RESAMPLE = None


def _resize_interpolate(img: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
    from PIL import Image

    if (img.shape[1], img.shape[0]) == (new_w, new_h):
        return img
    mode = Image.Resampling.LANCZOS if img.shape[0] < new_h else Image.Resampling.BILINEAR
    out = np.asarray(
        Image.fromarray((np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)).resize(
            (new_w, new_h), mode
        ),
        dtype=np.float32,
    ) / 255.0
    return out


def _upscale_mask(mask: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    from PIL import Image

    if (mask.shape[1], mask.shape[0]) == (out_w, out_h):
        return mask
    m8 = (np.clip(mask, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    up = np.asarray(
        Image.fromarray(m8).resize((out_w, out_h), Image.Resampling.LANCZOS),
        dtype=np.float32,
    ) / 255.0
    return np.clip(up, 0.0, 1.0)


@dataclass
class SegmentationParams:
    max_side: int = _MAX_INFERENCE_SIDE
    multi_scale: bool = True
    ensemble: bool = False


@dataclass
class SegmentResult:
    soft_mask: np.ndarray  # float32 [0,1] at full resolution
    engine_name: str
    inference_resolution: tuple[int, int]
    method: str


class SegmentationEngine:
    """Cache-friendly engine runner shared across the application."""

    def __init__(self, preset: str, models_folder: str | Path, device: str = "auto"):
        self.preset = preset
        self.models_folder = Path(models_folder)
        self.engine: ResolvedEngine | None = None

    def _ensure_engine(self, prefer_cuda: bool = True) -> ResolvedEngine:
        if self.engine is None:
            self.engine = resolve_engine(
                self.preset,
                self.models_folder,
                device="auto",
                prefer_cuda=prefer_cuda,
            )
        return self.engine

    def _predict_full_image(
        self,
        rgb: np.ndarray,
        max_side: int,
        scales: list[float],
    ) -> np.ndarray:
        engine = self._ensure_engine()
        h, w = rgb.shape[:2]

        results: list[np.ndarray] = []
        for scale in scales:
            tw = max(8, int(w * scale))
            th = max(8, int(h * scale))
            if max(tw, th) > max_side:
                k = max_side / max(tw, th)
                tw, th = max(8, int(tw * k)), max(8, int(th * k))
            tw = (tw // 8) * 8
            th = (th // 8) * 8
            if tw < 8:
                tw = 8
            if th < 8:
                th = 8

            small = _resize_interpolate(rgb, tw, th)
            mask_small = engine.run(small)
            if mask_small.shape[:2] != (th, tw):
                mask_small = _upscale_mask(mask_small, tw, th)
            results.append(mask_small)

        mean = np.mean(np.stack(results), axis=0)
        return mean

    def segment(
        self,
        rgb: np.ndarray,
        params: SegmentationParams | None = None,
        model_preset: str | None = None,
    ) -> SegmentResult:
        params = params or SegmentationParams()
        if model_preset and model_preset != self.preset:
            self.preset = model_preset
            self.engine = None

        self._ensure_engine()
        h, w = rgb.shape[:2]

        scales = [1.0]
        if params.multi_scale and params.max_side >= 768:
            scales = [1.0, 0.5]

        if params.ensemble and self.engine.name in ("u2net", "u2netp"):
            from app.models.torch_engine import U2NetEngine

            other = "u2netp" if self.engine.name == "u2net" else "u2net"
            ensure = None
            try:
                from app.models.download import ensure_u2net_weights

                ensure = ensure_u2net_weights(self.models_folder, [other])[other]
            except Exception:
                ensure = False
            if ensure:
                try:
                    from app.models.torch_engine import get_u2net_engine

                    alt = get_u2net_engine(other, self.models_folder, device=self._ensure_engine().handle.device)
                    alt.run = None
                    alt_rgb = _resize_interpolate(rgb, w // 2 or 1, h // 2 or 1)
                    alt_mask = _upscale_mask(self._run_torch(alt, alt_rgb), w, h)
                    base = self._predict_full_image(rgb, params.max_side, scales)
                    return SegmentResult(
                        soft_mask=np.clip((base + alt_mask) / 2.0, 0.0, 1.0),
                        engine_name=f"{self.engine.name}+{other}",
                        inference_resolution=(w, h),
                        method="ensemble",
                    )
                except Exception as exc:
                    log.warning("ensemble pass failed: %s", exc)

        mask = self._predict_full_image(rgb, params.max_side, scales)
        return SegmentResult(
            soft_mask=mask,
            engine_name=self.engine.name,
            inference_resolution=(w, h),
            method="multi_scale" if len(scales) > 1 else "single_scale",
        )

    @staticmethod
    def _run_torch(engine, small: np.ndarray) -> np.ndarray:
        import torch

        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        t = torch.from_numpy(np.transpose(small, (2, 0, 1))[None].astype(np.float32))
        t = (t - mean) / std
        with torch.no_grad():
            t = t.to(engine.device)
            out = engine.model(t)
            mask = out[0]
            if isinstance(mask, (tuple, list)):
                mask = mask[0]
            return np.clip(mask.squeeze(0).squeeze(0).float().cpu().numpy(), 0.0, 1.0)