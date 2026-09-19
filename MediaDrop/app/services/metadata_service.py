"""Metadata extraction service."""

from app.database.models import MediaMetadata
from app.extractors.yt_dlp_extractor import YtDlpExtractor
from app.utils.config import config_manager


class MetadataService:
    """Service for extracting and validating media metadata."""

    @staticmethod
    def extract_metadata(url: str) -> MediaMetadata:
        timeout = config_manager.get("network_timeout", 30)
        return YtDlpExtractor.extract(url, timeout=timeout)


metadata_service = MetadataService()
