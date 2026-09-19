"""Unified Media Service facade coordinating metadata, downloads, and conversions."""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.database.models import DownloadItem, MediaMetadata
from app.services.conversion_service import conversion_service
from app.services.download_service import DownloadService
from app.services.metadata_service import metadata_service
from app.services.thumbnail_service import thumbnail_service


class MediaService:
    """High-level service interface for MediaDrop operations."""

    def __init__(self):
        self.metadata = metadata_service
        self.downloader = DownloadService()
        self.thumbnail = thumbnail_service
        self.conversion = conversion_service

    def analyze_url(self, url: str) -> MediaMetadata:
        """Extract all metadata and available formats for a URL."""
        return self.metadata.extract_metadata(url)

    def download_media(
        self,
        task: DownloadItem,
        output_dir: Path,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        is_cancelled_func: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """Download video, audio or thumbnail."""
        if task.format_type.lower() == "thumbnail":
            # Thumbnail download
            format_name = task.quality if task.quality in ("JPG", "PNG", "WEBP") else "JPG"
            # If a custom thumbnail URL is present or from metadata
            thumb_url = task.thumbnail_url or task.url
            return self.thumbnail.download_thumbnail(
                url=thumb_url,
                output_dir=output_dir,
                base_name=f"{task.title}",
                target_format=format_name,
            )
        else:
            return self.downloader.execute_download(
                task=task,
                output_dir=output_dir,
                progress_callback=progress_callback,
                status_callback=status_callback,
                is_cancelled_func=is_cancelled_func,
            )


media_service = MediaService()
