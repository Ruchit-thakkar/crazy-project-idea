"""Configuration and settings manager."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    # General
    download_dir: str = field(
        default_factory=lambda: str(Path.home() / "Downloads" / "MediaDrop")
    )
    auto_open_completed: bool = False
    remember_last_dir: bool = True
    clipboard_detection: bool = True

    # Downloads
    max_concurrent_downloads: int = 3
    retry_count: int = 3
    network_timeout: int = 30
    speed_limit_kbs: int = 0
    auto_merge_streams: bool = True

    # Conversion
    default_audio_bitrate: str = "320k"
    default_thumbnail_format: str = "JPG"
    ffmpeg_path: str = ""

    # Appearance
    theme: str = "dark"

    # Advanced & Lifecycle
    debug_logging: bool = False
    first_run_completed: bool = False


class ConfigManager:
    """Manages reading and writing application configuration to config.json."""

    def __init__(self, config_file: Path | None = None):
        if config_file is None:
            config_file = Path(__file__).resolve().parent.parent.parent / "config.json"
        self.config_file = config_file
        self.config: AppConfig = self.load()

    def load(self) -> AppConfig:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Filter only fields present in AppConfig
                    valid_keys = AppConfig.__annotations__.keys()
                    filtered = {k: v for k, v in data.items() if k in valid_keys}
                    return AppConfig(**filtered)
            except Exception:
                return AppConfig()
        return AppConfig()

    def save(self) -> None:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.config), f, indent=4)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self.config, key, default)

    def set(self, key: str, value: Any) -> None:
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            self.save()

    def reset(self) -> None:
        self.config = AppConfig()
        self.save()


# Singleton instance
config_manager = ConfigManager()
