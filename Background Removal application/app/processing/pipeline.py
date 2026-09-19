"""The main processing pipeline.

    Original RGB (float32, full res)
        -> segmentation -> soft mask (full res)
        -> edge refinement (guided filter, defringe)
        -> optional alpha matting
        -> quality verification
        -> [manual refinement applied later in the UI]
        -> lossless PNG export
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.image.io import export_transparent_png
from app.matting.matting import apply_matting
from app.metadata.bundle import MetadataBundle
from app.models.registry import PRESETS
from app.processing.refine import refine_pipeline
from app.processing.verify import verify_floats
from app.segmentation.engine import SegmentationEngine, SegmentationParams
from app.utils.config import QualityVerificationResult
from app.utils.log import get_logger

log = get_logger("processing.pipeline")


@dataclass
class PipelineResult:
    rgb: np.ndarray               # float32 [0,1] full resolution (oriented)
    alpha: np.ndarray             # float32 [0,1] full resolution
    engine_name: str
    original_size: tuple[int, int]
    quality: str
    verification: QualityVerificationResult

    @property
    def passed(self) -> bool:
        return self.verification.passed


def resolve_inference_side(image_megapixels: float, quality: str, max_side_setting: int) -> int:
    """Pick the inference resolution trade-off for the selected quality."""
    if quality == "Ultra Quality":
        return max(1024, min(2048, max_side_setting))
    if quality == "High Quality":
        return min(1536, max_side_setting)
    return min(1024, max_side_setting)


class BackgroundRemovalPipeline:
    def __init__(
        self,
        models_folder: str | Path,
        preset: str = "Auto",
        quality: str = "Ultra Quality",
        device: str = "auto",
        max_inference_side: int = 1536,
    ):
        self.models_folder = Path(models_folder)
        self.preset = preset if preset in PRESETS else "Auto"
        self.quality = quality
        self.seg = SegmentationEngine(preset=self.preset, models_folder=self.models_folder, device=device)
        self.max_inference_side = max_inference_side

    def process(self, rgb: np.ndarray, progress=None) -> PipelineResult:
        """Run the full pipeline on a float32 RGB image at full resolution."""
        h, w = rgb.shape[:2]
        mp = (w * h) / 1_000_000.0
        side = resolve_inference_side(mp, self.quality, self.max_inference_side)

        if progress:
            progress(0.1, "segmenting...")
        seg_result = self.seg.segment(
            rgb,
            params=SegmentationParams(
                max_side=side,
                multi_scale=self.quality == "Ultra Quality",
            ),
        )
        mask = seg_result.soft_mask

        if progress:
            progress(0.5, "refining edges...")
        refined_rgb, alpha = refine_pipeline(rgb, mask, quality=self.quality)

        if progress:
            progress(0.7, "alpha matting...")
        if self.quality in ("High Quality", "Ultra Quality"):
            level = "ultra" if self.quality == "Ultra Quality" else "high"
            alpha = apply_matting(refined_rgb, alpha, level=level)

        if progress:
            progress(0.9, "verifying...")
        verification = verify_floats((w, h), refined_rgb, alpha)

        return PipelineResult(
            rgb=refined_rgb,
            alpha=np.asarray(alpha, np.float32),
            engine_name=seg_result.engine_name,
            original_size=(w, h),
            quality=self.quality,
            verification=verification,
        )

    def export(self, result: PipelineResult, output_path: str | Path, metadata: MetadataBundle | None = None, preserve_metadata: bool = True) -> Path:
        if not result.verification.passed:
            raise RuntimeError(
                "Refusing to export: quality verification failed.\n"
                + result.verification.summary()
            )
        return export_transparent_png(
            rgb_float=result.rgb,
            alpha_float=result.alpha,
            path=output_path,
            bit_depth=None,
            metadata=metadata,
            preserve_metadata=preserve_metadata,
        )