"""A small but complete U2-Net model wrapper with CPU/CUDA/MPS inference.

This is the primary in-house engine: fully torch-based, no external runtime.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.utils.exceptions import ModelLoadError, ModelNotFoundError
from app.utils.log import get_logger
from app.utils.system import detect_hardware

log = get_logger("models.torch_engine")

_LOCK = threading.Lock()
_INSTANCES: dict[tuple[str, str], "U2NetEngine"] = {}


@dataclass
class U2NetEngine:
    name: str  # "u2net" | "u2netp"
    weight_path: Path | None
    device: str
    model: object | None = None

    @property
    def lite(self) -> bool:
        return self.name == "u2netp"

    def load(self) -> "U2NetEngine":
        import torch

        from app.models import u2net

        if self.weight_path is None:
            raise ModelNotFoundError(
                f"Model weights for '{self.name}' were not found.\n"
                f"Download the weights into:\n    {self.weight_path}"
            )
        if not Path(self.weight_path).exists():
            raise ModelNotFoundError(
                f"Model file not found:\n    {self.weight_path}"
            )

        device = self.device
        net = u2net.build_u2net(lite=self.lite)
        try:
            state = torch.load(
                str(self.weight_path),
                map_location=torch.device("cpu"),
                weights_only=True,
            )
        except TypeError:
            state = torch.load(
                str(self.weight_path),
                map_location=torch.device("cpu"),
            )
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to read weights file '{Path(self.weight_path).name}': {exc}"
            ) from exc

        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        if hasattr(state, "state_dict"):
            state = state.state_dict()

        if hasattr(state, "keys"):
            fixed = {}
            for k, v in state.items():
                if k.startswith("module."):
                    k = k[len("module."):]
                fixed[k] = v
            state = fixed

        drift = None
        try:
            drift = net.load_state_dict(state, strict=False)
        except Exception as exc:
            raise ModelLoadError(
                f"Unable to apply weights to '{self.name}' architecture: {exc}"
            ) from exc
        if drift is not None and len(drift.missing_keys) > 0:
            log.warning("unexpected/missing keys: %s %s", drift.unexpected_keys[:5], drift.missing_keys[:5])

        try:
            net.to(device)
            net.eval()
        except Exception as exc:
            raise ModelLoadError(f"Failed to move model to {device}: {exc}") from exc
        self.model = net

        sanity = self.sanity_check()
        if not sanity:
            raise ModelLoadError(
                f"Sanity check failed for '{self.name}' — the loaded weights may be "
                f"incompatible. Remove the file and re-download."
            )
        return self

    def sanity_check(self, threshold: float = 0.55) -> bool:
        """Run a tiny forward pass; verify the output is finite and informative."""
        import torch

        if self.model is None:
            return False
        try:
            with torch.no_grad():
                t = torch.zeros(1, 3, 96, 96, device=self.device)
                t[:, :, 24:72, 24:72] = 0.5
                out = self.model(t)
                first = out[0]
                if isinstance(first, tuple):
                    first = first[0]
                first = first.detach().cpu().numpy()
            if not np.isfinite(first).all():
                return False
            vals = first.max() - first.min()
            return float(vals) >= threshold
        except Exception as exc:
            log.warning("sanity check error: %s", exc)
            return False


def get_u2net_engine(
    name: str,
    models_folder: str | Path,
    device: str = "auto",
    prefer_cuda: bool = True,
) -> U2NetEngine:
    """Return a shared (cached) U2NetEngine for the requested variant."""
    import torch

    if device == "auto":
        prof = detect_hardware(prefer_cuda=prefer_cuda)
        device = prof.device
    if not torch.cuda.is_available() and device == "cuda":
        device = "cpu"

    models_folder = Path(models_folder)
    weight = models_folder / (name + ".pth")

    key = (name, device)
    with _LOCK:
        if key in _INSTANCES:
            return _INSTANCES[key]
        engine = U2NetEngine(
            name=name,
            weight_path=weight,
            device=device,
        ).load()
        _INSTANCES[key] = engine
        return engine


def release_all() -> None:
    global _INSTANCES
    with _LOCK:
        _INSTANCES = {}


def is_model_available(name: str, models_folder: str | Path) -> bool:
    return (Path(models_folder) / (name + ".pth")).exists()


def available_models(models_folder: str | Path) -> list[str]:
    folder = Path(models_folder)
    found: list[str] = []
    for f in folder.glob("*.pth"):
        stem = f.stem.lower()
        if stem in ("u2net", "u2netp"):
            found.append(stem)
    return found