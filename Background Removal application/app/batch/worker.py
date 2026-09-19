"""Batch background removal with pause/resume/cancel and per-file isolation.

One file failing never stops the batch. Each input is processed fully in an
isolated unit of work and written directly to the output folder.

Parallelism: `settings.workers > 1` fans files out to a process pool — each
worker process loads its own model copy (spawn-safe on Windows because every
task arg is picklable primitives/dataclasses).
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from app.utils.log import get_logger

log = get_logger("batch.worker")

SUPPORTED = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp")


@dataclass
class BatchSettings:
    preset: str = "Auto"
    quality: str = "Ultra Quality"
    output_folder: str = ""
    preserve_metadata: bool = True
    background_mode: str = "Transparent"
    background_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    blur_radius: float = 16.0
    overwrite: bool = False
    max_inference_side: int = 1536
    output_prefix: str = ""
    save_to_source_dir: bool = False
    workers: int = 1


@dataclass
class ItemResult:
    input_path: str
    output_path: str
    status: str  # "ok" | "failed" | "skipped"
    seconds: float = 0.0
    error: str = ""
    output_size: tuple[int, int] = (0, 0)


def process_one(task: dict) -> ItemResult:
    """Module-level, picklable unit of work for the process pool."""
    import numpy as np

    from app.image.loader import load
    from app.image.io import export_transparent_png
    from app.metadata.bundle import MetadataBundle
    from app.processing.background import TRANSPARENT, compose
    from app.processing.pipeline import BackgroundRemovalPipeline
    from app.processing.verify import verify_file

    path = Path(task["input"])
    out_path = Path(task["output"])
    models_folder = task["models_folder"]

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return ItemResult(str(path), str(out_path), "failed", error=f"cannot create output: {exc}")

    if out_path.exists() and not task.get("overwrite", False):
        return ItemResult(str(path), str(out_path), "skipped", error="output already exists")

    try:
        pipeline = BackgroundRemovalPipeline(
            models_folder=models_folder,
            preset=task.get("preset", "Auto"),
            quality=task.get("quality", "Ultra Quality"),
            max_inference_side=task.get("max_inference_side", 1536),
        )
        loaded = load(path)
        result = pipeline.process(loaded.rgb, progress=None)

        if task.get("background_mode", TRANSPARENT) != TRANSPARENT:
            rgb_c, alpha_c = compose(
                result.rgb,
                result.alpha,
                mode=task["background_mode"],
                color=tuple(task.get("background_color", [1.0, 1.0, 1.0])),
                blur_radius=task.get("blur_radius", 16.0),
            )
        else:
            rgb_c, alpha_c = result.rgb, result.alpha

        meta = MetadataBundle.from_loaded(loaded)
        export_transparent_png(
            rgb_c,
            alpha_c,
            str(out_path),
            bit_depth=loaded.bit_depth,
            metadata=meta,
            preserve_metadata=task.get("preserve_metadata", True),
        )

        ok = verify_file(loaded.info.effective_size, out_path)
        if not ok.passed:
            out_path.unlink(missing_ok=True)
            return ItemResult(
                str(path), str(out_path), "failed",
                error="; ".join(ok.errors), output_size=ok.output_size,
            )
        return ItemResult(str(path), str(out_path), "ok", output_size=ok.output_size)
    except Exception as exc:
        log.warning("failed %s: %s", path.name, exc)
        return ItemResult(str(path), str(out_path), "failed", error=str(exc))


class BatchProcessor:
    """Runs a batch in the calling thread — drive it from a QThread.

    Callbacks:
      on_progress(result, done, total, eta_s, fps)
      on_file_done(result)
      on_complete(results)
      on_cancelled(results)
      on_error(message)
    """

    def __init__(self, paths: list[str | Path], settings: BatchSettings, callbacks: dict[str, Callable] | None = None):
        self.paths = [Path(p) for p in paths]
        self.settings = settings
        self.callbacks = callbacks or {}
        self.results: list[ItemResult] = []
        self._pause_event = None
        self._cancel_event = None

    def attach_events(self, pause_event, cancel_event) -> None:
        self._pause_event = pause_event
        self._cancel_event = cancel_event

    def pause(self) -> None:
        if self._pause_event:
            self._pause_event.set()

    def resume(self) -> None:
        if self._pause_event:
            self._pause_event.clear()

    def cancel(self) -> None:
        if self._cancel_event:
            self._cancel_event.set()

    def failed_paths(self) -> list[Path]:
        return [Path(r.input_path) for r in self.results if r.status == "failed"]

    def run(self) -> None:
        try:
            self._run_inner()
        except Exception as exc:
            log.exception("batch crashed")
            self._emit("on_error", str(exc))

    def _run_inner(self) -> None:
        total = len(self.paths)
        done = 0
        window: list[float] = []
        workers = max(1, self.settings.workers)

        if workers == 1:
            for idx, path in enumerate(self.paths):
                if self._cancelled():
                    break
                self._wait_if_paused()
                if self._cancelled():
                    break
                t0 = time.perf_counter()
                result = self._run_one(path)
                dt = time.perf_counter() - t0
                result.seconds = dt
                self.results.append(result)
                done += 1
                window.append(dt)
                window = window[-30:]
                avg = np.mean(window)
                fps = 1.0 / max(avg, 1e-6)
                eta = avg * (total - done)
                self._emit("on_progress", result, done, total, eta, fps)
                self._emit("on_file_done", result)
        else:
            tasks = self._make_tasks()
            submitted = False
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(process_one, t) for t in tasks]
                submitted = True
                for f in as_completed(futures):
                    if self._cancelled():
                        for fut in futures:
                            fut.cancel()
                        break
                    self._wait_if_paused()
                    try:
                        result = f.result()
                    except Exception as exc:
                        result = ItemResult("", "", "failed", error=str(exc))
                    self.results.append(result)
                    done += 1
                    dt = result.seconds or 0.0
                    window.append(dt)
                    window = window[-30:]
                    avg = np.mean(window) or 0.0
                    fps = 1.0 / max(avg, 1e-6)
                    eta = avg * (total - done)
                    self._emit("on_progress", result, done, total, eta, fps)
                    self._emit("on_file_done", result)

        if self._cancelled():
            self._emit("on_cancelled", self.results)
        else:
            self._emit("on_complete", self.results)

    def _cancelled(self) -> bool:
        return bool(self._cancel_event and self._cancel_event.is_set())

    def _wait_if_paused(self) -> None:
        while self._pause_event and self._pause_event.is_set():
            if self._cancelled():
                return
            time.sleep(0.1)

    def _resolve_output_dir(self, path: Path) -> Path:
        s = self.settings
        if s.output_folder and not s.save_to_source_dir:
            return Path(s.output_folder)
        if s.output_folder and s.save_to_source_dir:
            return Path(s.output_folder)
        return path.parent / "bg_remove_output"

    def _run_one(self, path: Path) -> ItemResult:
        out_dir = self._resolve_output_dir(path)
        prefix = self.settings.output_prefix
        out_path = out_dir / f"{prefix}{path.stem}.png"
        task = self._make_task(path, out_path)
        return process_one(task)

    def _make_task(self, path: Path, out_path: Path) -> dict:
        from app.utils.config import models_dir

        return {
            "input": str(path),
            "output": str(out_path),
            "models_folder": str(models_dir()),
            "preset": self.settings.preset,
            "quality": self.settings.quality,
            "max_inference_side": self.settings.max_inference_side,
            "background_mode": self.settings.background_mode,
            "background_color": list(self.settings.background_color),
            "blur_radius": self.settings.blur_radius,
            "preserve_metadata": self.settings.preserve_metadata,
            "overwrite": self.settings.overwrite,
        }

    def _make_tasks(self) -> list[dict]:
        tasks = []
        for path in self.paths:
            out_dir = self._resolve_output_dir(path)
            prefix = self.settings.output_prefix
            out_path = out_dir / f"{prefix}{path.stem}.png"
            tasks.append(self._make_task(path, out_path))
        return tasks

    def _emit(self, name: str, *args) -> None:
        cb = self.callbacks.get(name)
        if cb:
            try:
                cb(*args)
            except Exception:
                log.exception("callback %s failed", name)


def discover_images(folder: Path) -> list[Path]:
    """Recursively collect supported images under a folder."""
    out: list[Path] = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in SUPPORTED:
                out.append(p)
    out.sort(key=lambda p: p.name.lower())
    return out