"""Data models for MediaDrop."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid


@dataclass
class VideoQuality:
    resolution: str  # e.g. "1080p", "720p"
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    vcodec: str = "Unknown"
    acodec: str = "Unknown"
    filesize_est: Optional[int] = None
    format_id: str = ""
    container: str = "mp4"
    has_audio: bool = False
    needs_merge: bool = True
    bitrate: Optional[float] = None


@dataclass
class AudioQuality:
    bitrate: str  # e.g. "320 kbps", "256 kbps"
    bitrate_num: int = 320
    filesize_est: Optional[int] = None
    format: str = "MP3"
    duration: Optional[float] = None


@dataclass
class ThumbnailQuality:
    label: str  # "Original", "High", "Medium", "Low"
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    resolution_str: str = ""


@dataclass
class MediaMetadata:
    url: str
    title: str = "Not available"
    channel: str = "Not available"
    platform: str = "Unknown"
    duration: Optional[float] = None
    upload_date: str = "Not available"
    language: str = "Not available"
    visibility: str = "Public"
    media_type: str = "Video"
    caption: str = "Not available"
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    thumbnail_url: str = ""
    video_qualities: List[VideoQuality] = field(default_factory=list)
    audio_qualities: List[AudioQuality] = field(default_factory=list)
    thumbnail_qualities: List[ThumbnailQuality] = field(default_factory=list)


@dataclass
class DownloadItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    url: str = ""
    title: str = ""
    platform: str = ""
    format_type: str = "video"  # "video", "audio", "thumbnail"
    quality: str = ""  # "1080p", "320 kbps", "Original"
    selected_format_id: str = ""
    file_path: str = ""
    file_size: int = 0
    status: str = "Queued"  # "Queued", "Analyzing", "Downloading", "Processing", "Merging", "Converting", "Completed", "Paused", "Cancelled", "Failed"
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: str = "0 B/s"
    eta: str = "--:--"
    error_message: str = ""
    thumbnail_url: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class HistoryRecord:
    id: Optional[int] = None
    title: str = ""
    url: str = ""
    platform: str = ""
    format_type: str = ""
    quality: str = ""
    file_path: str = ""
    file_size: int = 0
    status: str = "Completed"
    thumbnail_url: str = ""
    downloaded_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
