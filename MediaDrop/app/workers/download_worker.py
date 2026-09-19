"""Asynchronous worker for media downloads."""

from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QThread, Signal

from app.database.models import DownloadItem
from app.services.download_service import DownloadCancelledException
from app.services.media_service import media_service
from app.utils.logger import logger


class DownloadWorker(QThread):
    """Worker thread that executes media downloads without blocking the UI."""

    status_changed = Signal(str, str)  # (task_id, new_status)
    progress_updated = Signal(str, float, str, str, int, int)  # (task_id, pct, speed, eta, downloaded, total)
    download_finished = Signal(str, str, int)  # (task_id, file_path, file_size)
    download_error = Signal(str, str, str)  # (task_id, friendly_msg, technical_details)
    download_cancelled = Signal(str)  # (task_id)

    def __init__(self, task: DownloadItem, output_dir: Path, parent=None):
        super().__init__(parent)
        self.task = task
        self.output_dir = output_dir
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        logger.info(f"Starting download task {self.task.id}: {self.task.title} ({self.task.quality})")
        self.status_changed.emit(self.task.id, "Downloading")

        def progress_cb(data: Dict[str, Any]):
            status = data.get("status", "Downloading")
            self.status_changed.emit(self.task.id, status)
            pct = data.get("progress", 0.0)
            speed = data.get("speed", "0 B/s")
            eta = data.get("eta", "--:--")
            downloaded = data.get("downloaded_bytes", 0)
            total = data.get("total_bytes", 0)
            self.progress_updated.emit(self.task.id, pct, speed, eta, downloaded, total)

        def status_cb(status_name: str):
            self.status_changed.emit(self.task.id, status_name)

        try:
            result_path = media_service.download_media(
                task=self.task,
                output_dir=self.output_dir,
                progress_callback=progress_cb,
                status_callback=status_cb,
                is_cancelled_func=self.is_cancelled,
            )

            file_size = result_path.stat().st_size if result_path.exists() else 0
            self.status_changed.emit(self.task.id, "Completed")
            self.download_finished.emit(self.task.id, str(result_path), file_size)
            logger.info(f"Download finished: {result_path} ({file_size} bytes)")

        except DownloadCancelledException:
            logger.info(f"Download task {self.task.id} cancelled")
            self.status_changed.emit(self.task.id, "Cancelled")
            self.download_cancelled.emit(self.task.id)

        except RuntimeError as re:
            err_text = str(re)
            if "|||" in err_text:
                friendly, detail = err_text.split("|||", 1)
            else:
                friendly = "Download failed"
                detail = err_text
            self.status_changed.emit(self.task.id, "Failed")
            self.download_error.emit(self.task.id, friendly, detail)

        except Exception as e:
            logger.error(f"Unexpected download failure for {self.task.id}: {e}")
            self.status_changed.emit(self.task.id, "Failed")
            self.download_error.emit(self.task.id, "Download failed", str(e))
