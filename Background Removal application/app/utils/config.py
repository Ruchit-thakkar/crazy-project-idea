"""Application configuration and path management."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def app_root() -> Path:
    """The project root folder (where main.py / requirements.txt live)."""
    # main.py is two levels up from app/.../utils/config.py
    return Path(__file__).resolve().parents[2]


def models_dir() -> Path:
    return app_root() / "models"


def output_dir() -> Path:
    return app_root() / "output"


def settings_dir() -> Path:
    p = Path(os.environ.get("LOCALAPPDATA", Path.home())).joinpath("BgRemove")
    return p


def settings_file() -> Path:
    return settings_dir() / "settings.json"


@dataclass
class AppSettings:
    """Persisted application settings.

    All fields are serialisable to JSON so the UI can round-trip them.
    """

    # --- Device ---
    prefer_cuda: bool = True
    device: str = "auto"  # auto | cuda | cpu | mps

    # --- Processing ---
    model_preset: str = "Auto"  # Auto | Fast | High Quality | Human | Product | Hair/Fur
    quality: str = "Ultra"  # Standard | High Quality | Ultra Quality
    enable_matting: bool = True
    matting_level: str = "high"  # standard | high | ultra
    max_inference_side: int = 1536
    use_fp16: bool = True
    preserve_metadata: bool = True
    auto_enhance_edges: bool = True
    halo_removal: bool = True
    blur_radius: float = 12.0

    # --- Output ---
    output_folder: str = ""
    output_prefix: str = ""
    overwrite: bool = False

    # --- Batch ---
    workers: int = 1  # parallel processes / threads for batch (0 -> auto)
    tile_megapixels: float = 64.0  # above this, tile the image for matting/refine

    # --- UI ---
    theme: str = "dark"
    last_input_folder: str = ""
    last_output_folder: str = ""

    @classmethod
    def defaults(cls) -> "AppSettings":
        return cls()

    def load(self) -> "AppSettings":
        try:
            data = json.loads(settings_file().read_text(encoding="utf-8"))
            known = {f for f in self.__dataclass_fields__}
            for key, value in data.items():
                if key in known and isinstance(value, type(getattr(self, key, None))):
                    setattr(self, key, value)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return self

    def save(self) -> None:
        try:
            settings_dir().mkdir(parents=True, exist_ok=True)
            settings_file().write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass


@dataclass
class QualityVerificationResult:
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    has_alpha: bool
    is_lossless_png: bool
    rgb_preserved: bool
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        o = self.original_size
        out = self.output_size
        lines = [
            f"Original: {o[0]} x {o[1]}",
            f"Output:   {out[0]} x {out[1]}",
        ]
        if self.errors:
            lines.append("Resolution preserved FAIL")
            lines += [f"  - {e}" for e in self.errors]
        else:
            lines.append("Resolution preserved OK")
        if self.has_alpha:
            lines.append("Transparent background OK")
        else:
            lines.append("Transparent background FAIL")
        if self.is_lossless_png:
            lines.append("Lossless PNG OK")
        else:
            lines.append("Lossless PNG FAIL")
        return "\n".join(lines)