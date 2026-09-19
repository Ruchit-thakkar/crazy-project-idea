"""Main application controller managing queue, workers, and history synchronization."""

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from app.database.database import db
from app.database.models import DownloadItem, HistoryRecord, MediaMetadata
from app.utils.config import config_manager
from app.utils.file_utils import open_file_in_os
from app.utils.logger import logger
from app.workers.analyze_worker import AnalyzeWorker
from app.workers.download_worker import DownloadWorker


class MainController(QObject):
    """Central application controller orchestrating downloads, analysis, and data storage."""

    # Signals for UI updates
    analysis_started = Signal(str)
    analysis_finished = Signal(object)  # MediaMetadata
    analysis_error = Signal(str, str)   # friendly, details

    task_added = Signal(object)         # DownloadItem
    task_updated = Signal(object)       # DownloadItem
    task_removed = Signal(str)          # task_id
    active_count_changed = Signal(int)  # number of currently downloading items
    notification_requested = Signal(str, str)  # title, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: Dict[str, DownloadItem] = {}
        self.workers: Dict[str, DownloadWorker] = {}
        self.queue: List[str] = []  # List of task IDs waiting to download
        self.analyze_worker: Optional[AnalyzeWorker] = None

    def start_analysis(self, url: str) -> None:
        """Start async URL analysis."""
        if self.analyze_worker and self.analyze_worker.isRunning():
            self.analyze_worker.terminate()
            self.analyze_worker.wait()

        self.analysis_started.emit(url)
        self.analyze_worker = AnalyzeWorker(url, parent=self)
        self.analyze_worker.analysis_finished.connect(self._on_analysis_finished)
        self.analyze_worker.analysis_error.connect(self._on_analysis_error)
        self.analyze_worker.start()

    def _on_analysis_finished(self, metadata: MediaMetadata) -> None:
        self.analysis_finished.emit(metadata)

    def _on_analysis_error(self, friendly: str, details: str) -> None:
        self.analysis_error.emit(friendly, details)

    def enqueue_download(self, item: DownloadItem) -> None:
        """Add a new download item to the queue."""
        self.tasks[item.id] = item
        self.queue.append(item.id)
        self.task_added.emit(item)
        logger.info(f"Enqueued download task: {item.title} ({item.quality})")
        self._process_queue()

    def _process_queue(self) -> None:
        """Start pending downloads up to max_concurrent limit."""
        max_concurrent = config_manager.get("max_concurrent_downloads", 3)
        running_count = len(self.workers)

        while running_count < max_concurrent and self.queue:
            task_id = self.queue.pop(0)
            item = self.tasks.get(task_id)
            if not item:
                continue

            # Check output dir
            custom_dir = config_manager.get("download_dir")
            output_dir = Path(custom_dir) if custom_dir else Path.home() / "Downloads" / "MediaDrop"
            output_dir.mkdir(parents=True, exist_ok=True)

            worker = DownloadWorker(item, output_dir=output_dir, parent=self)
            worker.status_changed.connect(self._on_worker_status_changed)
            worker.progress_updated.connect(self._on_worker_progress_updated)
            worker.download_finished.connect(self._on_worker_download_finished)
            worker.download_error.connect(self._on_worker_download_error)
            worker.download_cancelled.connect(self._on_worker_download_cancelled)

            self.workers[task_id] = worker
            worker.start()
            running_count += 1

        self.active_count_changed.emit(len(self.workers))

    def _on_worker_status_changed(self, task_id: str, new_status: str) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].status = new_status
            self.task_updated.emit(self.tasks[task_id])

    def _on_worker_progress_updated(
        self,
        task_id: str,
        pct: float,
        speed: str,
        eta: str,
        downloaded: int,
        total: int,
    ) -> None:
        if task_id in self.tasks:
            item = self.tasks[task_id]
            item.progress = pct
            item.speed = speed
            item.eta = eta
            item.downloaded_bytes = downloaded
            item.total_bytes = total
            self.task_updated.emit(item)

    def _on_worker_download_finished(self, task_id: str, file_path: str, file_size: int) -> None:
        if task_id in self.tasks:
            item = self.tasks[task_id]
            item.status = "Completed"
            item.progress = 100.0
            item.file_path = file_path
            item.file_size = file_size
            self.task_updated.emit(item)

            # Persist to database history
            record = HistoryRecord(
                title=item.title,
                url=item.url,
                platform=item.platform,
                format_type=item.format_type,
                quality=item.quality,
                file_path=file_path,
                file_size=file_size,
                status="Completed",
                thumbnail_url=item.thumbnail_url,
            )
            db.add_history(record)

            # Notification
            self.notification_requested.emit("Download Complete", f"{item.title}")

            # Auto-open if configured
            if config_manager.get("auto_open_completed", False):
                open_file_in_os(file_path)

        if task_id in self.workers:
            del self.workers[task_id]

        self._process_queue()

    def _on_worker_download_error(self, task_id: str, friendly: str, details: str) -> None:
        if task_id in self.tasks:
            item = self.tasks[task_id]
            item.status = "Failed"
            item.error_message = friendly
            self.task_updated.emit(item)

            # Persist failed attempt in history
            record = HistoryRecord(
                title=item.title,
                url=item.url,
                platform=item.platform,
                format_type=item.format_type,
                quality=item.quality,
                file_path="",
                file_size=0,
                status="Failed",
                thumbnail_url=item.thumbnail_url,
            )
            db.add_history(record)

        if task_id in self.workers:
            del self.workers[task_id]

        self._process_queue()

    def _on_worker_download_cancelled(self, task_id: str) -> None:
        if task_id in self.tasks:
            item = self.tasks[task_id]
            item.status = "Cancelled"
            self.task_updated.emit(item)

        if task_id in self.workers:
            del self.workers[task_id]

        self._process_queue()

    def pause_download(self, task_id: str) -> None:
        """Pause / cancel active download and set status to Paused."""
        if task_id in self.workers:
            worker = self.workers[task_id]
            worker.cancel()
        elif task_id in self.queue:
            self.queue.remove(task_id)

        if task_id in self.tasks:
            self.tasks[task_id].status = "Paused"
            self.task_updated.emit(self.tasks[task_id])

    def resume_download(self, task_id: str) -> None:
        """Resume paused or retry failed download."""
        if task_id in self.tasks:
            item = self.tasks[task_id]
            item.status = "Queued"
            item.progress = 0.0
            item.error_message = ""
            self.task_updated.emit(item)
            if task_id not in self.queue and task_id not in self.workers:
                self.queue.append(task_id)
                self._process_queue()

    def cancel_download(self, task_id: str) -> None:
        """Cancel download."""
        if task_id in self.workers:
            self.workers[task_id].cancel()
        elif task_id in self.queue:
            self.queue.remove(task_id)

        if task_id in self.tasks:
            self.tasks[task_id].status = "Cancelled"
            self.task_updated.emit(self.tasks[task_id])

    def retry_download(self, task_id: str) -> None:
        self.resume_download(task_id)

    def remove_task(self, task_id: str) -> None:
        """Remove task card from UI list."""
        if task_id in self.workers:
            self.workers[task_id].cancel()
        if task_id in self.queue:
            self.queue.remove(task_id)
        if task_id in self.tasks:
            del self.tasks[task_id]
        self.task_removed.emit(task_id)

    def clear_completed(self) -> None:
        """Remove all completed, cancelled, or failed items from active task list."""
        to_remove = [
            tid for tid, task in self.tasks.items()
            if task.status in ("Completed", "Cancelled", "Failed")
        ]
        for tid in to_remove:
            self.remove_task(tid)

    def get_all_tasks(self) -> List[DownloadItem]:
        return list(self.tasks.values())


main_controller = MainController()
