"""Optional ONNX Runtime engine for exported bg-removal models.

Lets advanced users drop in proven ONNX exports of IS-Net, MODNet or U2-Net
(e.g. ``isnet-general-use.onnx``, ``modnet.onnx``, ``u2net.onnx``) without us
reproducing their architectures. Requires: ``pip install onnxruntime``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.utils.exceptions import ModelLoadError, ModelNotFoundError
from app.utils.log import get_logger
from app.utils.system import detect_hardware

log = get_logger("models.onnx_engine")

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)


@dataclass
class OnnxEngine:
    name: str
    path: Path
    session: object | None = None
    input_name: str = ""
    input_size: tuple[int, int] = (0, 0)

    # u2net-style: ImageNet normalization + sigmoid post.
    imagenet_norm: bool = False
    # modnet-style: plain 0..1 normalization + optional 4th "hint" channel.
    add_hint_channel: bool = False
    single_output: bool = False

    @property
    def available(self) -> bool:
        return self.session is not None

    def load(self) -> "OnnxEngine":
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ModelLoadError(
                "ONNX engine requires onnxruntime. Install with: pip install onnxruntime"
            ) from exc

        if not self.path.exists():
            raise ModelNotFoundError(f"ONNX model not found: {self.path}")

        providers = ["CPUExecutionProvider"]
        prof = detect_hardware(prefer_cuda=True)
        if prof.device == "cuda":
            try:
                import onnxruntime.tools  # noqa: F401
                providers.insert(0, "CUDAExecutionProvider")
            except Exception:
                pass

        try:
            self.session = ort.InferenceSession(str(self.path), providers=providers)
            inp = self.session.get_inputs()[0]
            self.input_name = inp.name
            shape = list(inp.shape)
            if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                self.input_size = (shape[3], shape[2])
            self.single_output = len(self.session.get_outputs()) == 1
        except Exception as exc:
            raise ModelLoadError(f"Failed to load ONNX session '{self.path.name}': {exc}") from exc
        return self

    def _resize(self, img8: np.ndarray, tw: int, th: int) -> np.ndarray:
        from PIL import Image

        ih, iw = img8.shape[:2]
        if (iw, ih) == (tw, th):
            return img8
        method = Image.Resampling.LANCZOS if max(ih, iw) > max(tw, th) else Image.Resampling.BILINEAR
        return np.asarray(Image.fromarray(img8).resize((tw, th), method), dtype=np.uint8)

    def _normalize(self, rgb: np.ndarray, size: tuple[int, int]) -> tuple[np.ndarray, tuple[int, int]]:
        h, w = rgb.shape[:2]
        if size and size[0] > 0:
            img = np.asarray(np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5, dtype=np.uint8)
            x = self._resize(img, *size).astype(np.float32) / 255.0
        else:
            x = rgb.astype(np.float32)

        if self.imagenet_norm:
            x = (x - _IMAGENET_MEAN) / _IMAGENET_STD
        elif self.add_hint_channel:
            x = np.concatenate([x, np.ones_like(x[:, :1])], axis=1)
        return x.astype(np.float32), (w, h)

    def run(self, rgb: np.ndarray) -> np.ndarray:
        """Return a soft alpha mask in [0,1] at the input resolution."""
        if self.session is None:
            raise ModelLoadError("ONNX session not initialised")
        img, (_w, _h) = self._normalize(rgb, self.input_size)
        outputs = self.session.run(None, {self.input_name: img})
        if not outputs:
            raise ModelLoadError("No ONNX outputs returned")

        out = outputs[0]
        if self.single_output:
            out0 = outputs[0]
        else:
            # matting models typically produce matting first; pick the largest
            # two-dimensional output as the alpha candidate.
            out0 = outputs[0]

        if out0.ndim == 4:
            ch = out0.shape[1]
            if ch >= 4:
                soft = out0[:, 1] + out0[:, 2]
            else:
                soft = out0[:, 0] if ch == 1 else out0[:, :1].mean(axis=1)
        elif out0.ndim == 3:
            soft = out0
        else:
            soft = out0[..., np.newaxis]
        soft = soft[0]  # NCHW -> HW
        soft = soft.astype(np.float32)

        if float(soft.max()) > 1.5:
            soft = soft / 255.0
        soft = np.clip(soft, 0.0, 1.0)

        h, w = rgb.shape[:2]
        oh, ow = soft.shape[:2]
        if (oh, ow) != (h, w):
            from PIL import Image

            soft8 = np.clip(soft, 0.0, 1.0) * 255.0
            soft8 = soft8.astype(np.uint8)
            soft = np.asarray(
                Image.fromarray(soft8).resize((w, h), Image.Resampling.BILINEAR),
                dtype=np.float32,
            ) / 255.0
        return soft