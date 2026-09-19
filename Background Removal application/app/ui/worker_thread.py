"""QThread wrappers that keep AI + heavy work off the UI thread."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.batch.worker import BatchProcessor, BatchSettings
from app.processing.pipeline import BackgroundRemovalPipeline
from app.utils.log import get_logger

log = get_logger("ui.threads")


class SingleProcessWorker(QThread):
    """Processes one loaded image in the background."""

    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(float, str)

    def __init__(self, rgb, preset: str, quality: str, max_inference_side: int = 1536, parent=None):
        super().__init__(parent)
        self._rgb = rgb
        self._preset = preset
        self._quality = quality
        self._max_inference_side = max_inference_side

    def run(self):
        from app.utils.config import models_dir

        try:
            pipe = BackgroundRemovalPipeline(
                models_folder=models_dir(),
                preset=self._preset,
                quality=self._quality,
                max_inference_side=self._max_inference_side,
            )

            def cb(v, label):
                self.progress.emit(float(v), str(label))

            result = pipe.process(self._rgb, progress=cb)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            log.exception("single processing failed")
            self.failed.emit(str(exc))


class RefineWorker(QThread):
    """Runs mask-heavy refinement (guided filter etc.) off the UI thread."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, rgb, alpha, quality: str = "Ultra Quality", parent=None):
        super().__init__(parent)
        self._rgb = rgb
        self._alpha = alpha
        self._quality = quality

    def run(self):
        from app.processing.refine import refine_pipeline

        try:
            _, refined = refine_pipeline(self._rgb, self._alpha, quality=self._quality)
            self.finished_ok.emit(refined)
        except Exception as exc:
            log.exception("refine failed")
            self.failed.emit(str(exc))


class BatchWorker(QThread):
    """Drives a BatchProcessor and mirrors its callbacks onto Qt signals."""

    progress = Signal(object, int, int, float, float)   # result, done, total, eta, fps
    file_done = Signal(object)
    complete = Signal(object)
    cancelled = Signal(object)
    error = Signal(str)

    def __init__(self, paths, settings: BatchSettings, parent=None):
        super().__init__(parent)
        self._processor = BatchProcessor(
            paths, settings, callbacks={
                "on_progress": self._on_progress,
                "on_file_done": self._on_file_done,
                "on_complete": self._on_complete,
                "on_cancelled": self._on_cancelled,
                "on_error": self._on_error,
            },
        )
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()
        self._processor.attach_events(self._pause_event, self._cancel_event)

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def cancel(self):
        self._cancel_event.set()

    def failed_paths(self):
        return self._processor.failed_paths()

    def _on_progress(self, result, done, total, eta, fps):
        self.progress.emit(result, done, total, eta, fps)

    def _on_file_done(self, result):
        self.file_done.emit(result)

    def _on_complete(self, results):
        self.complete.emit(results)

    def _on_cancelled(self, results):
        self.cancelled.emit(results)

    def _on_error(self, msg):
        self.error.emit(msg)

    def run(self):
        self._processor.run()