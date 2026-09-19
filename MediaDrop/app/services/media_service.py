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
        fmt_lower = task.format_type.lower()
        if fmt_lower in ("thumbnail", "image"):
            format_name = task.quality if task.quality in ("JPG", "PNG", "WEBP") else "JPG"

            # Check if this is a multi-image / gallery task
            if task.custom_urls and len(task.custom_urls) > 1:
                from app.utils.file_utils import sanitize_filename
                gallery_folder = output_dir / sanitize_filename(task.title)
                gallery_folder.mkdir(parents=True, exist_ok=True)
                total_imgs = len(task.custom_urls)

                for idx, img_url in enumerate(task.custom_urls):
                    if is_cancelled_func and is_cancelled_func():
                        from app.services.download_service import DownloadCancelledException
                        raise DownloadCancelledException("Image download cancelled")

                    self.thumbnail.download_thumbnail(
                        url=img_url,
                        output_dir=gallery_folder,
                        base_name=f"photo_{idx + 1:02d}",
                        target_format=format_name,
                    )

                    pct = float((idx + 1) / total_imgs * 100.0)
                    if progress_callback:
                        progress_callback({
                            "status": "Downloading",
                            "progress": pct,
                            "downloaded_bytes": idx + 1,
                            "total_bytes": total_imgs,
                            "speed": f"{idx + 1}/{total_imgs} images",
                            "eta": "",
                        })

                if progress_callback:
                    progress_callback({"status": "Completed", "progress": 100.0})
                return gallery_folder

            # Single image / thumbnail
            tag = "[thumbnail]" if fmt_lower == "thumbnail" else ""
            img_url = (task.custom_urls[0] if task.custom_urls else None) or task.thumbnail_url or task.url
            result_path = self.thumbnail.download_thumbnail(
                url=img_url,
                output_dir=output_dir,
                base_name=f"{task.title}",
                target_format=format_name,
                suffix_tag=tag,
            )
            if progress_callback:
                progress_callback({"status": "Completed", "progress": 100.0})
            return result_path
        else:
            return self.downloader.execute_download(
                task=task,
                output_dir=output_dir,
                progress_callback=progress_callback,
                status_callback=status_callback,
                is_cancelled_func=is_cancelled_func,
            )


media_service = MediaService()
