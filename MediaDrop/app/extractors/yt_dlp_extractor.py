"""Safe yt-dlp metadata extractor and platform detector."""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import yt_dlp

from app.database.models import (
    AudioQuality,
    ImageItem,
    MediaMetadata,
    ThumbnailQuality,
    VideoQuality,
)
from app.extractors.image_extractor import ImageExtractor, is_direct_image_url
from app.utils.logger import logger


def detect_platform(url: str) -> str:
    """Identify platform from URL hostname."""
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        if "youtube.com" in netloc or "youtu.be" in netloc:
            return "YouTube"
        elif "instagram.com" in netloc:
            return "Instagram"
        elif "tiktok.com" in netloc:
            return "TikTok"
        elif "facebook.com" in netloc or "fb.watch" in netloc:
            return "Facebook"
        elif "twitter.com" in netloc or "x.com" in netloc:
            return "X"
        elif "pinterest.com" in netloc or "pin.it" in netloc:
            return "Pinterest"
        elif netloc:
            # Clean domain name as generic platform
            parts = netloc.split(".")
            if len(parts) >= 2:
                return parts[-2].capitalize()
            return netloc.capitalize()
    except Exception:
        pass
    return "Unknown"


def parse_extractor_error(error_str: str) -> Tuple[str, str]:
    """Return user-friendly message and technical detail from yt-dlp error."""
    lower = error_str.lower()
    if "is not a valid url" in lower or "unsupported url" in lower:
        return "Invalid URL", "The provided link is not a recognized or supported media URL."
    elif "private video" in lower or "this video is private" in lower:
        return "The media is private", "This content has been set to private by its creator."
    elif "sign in" in lower or "login" in lower or "confirm you're not a bot" in lower:
        return "Authentication required", "This content requires platform authentication or login."
    elif "members-only" in lower or "paid" in lower:
        return "Protected content", "This content is restricted to subscribers or paid members."
    elif "video unavailable" in lower or "not available" in lower:
        return "The media is unavailable", "The media has been deleted or is not accessible."
    elif "timed out" in lower or "connection refused" in lower or "name or service not known" in lower:
        return "Network connection failed", "Unable to connect to the platform server. Check your network."
    elif "ffmpeg" in lower:
        return "FFmpeg processing error", "An issue occurred while processing media with FFmpeg."
    return "Unable to access media", error_str


class YtDlpExtractor:
    """Wrapper around yt-dlp for extracting media metadata without downloading."""

    @staticmethod
    def extract(url: str, timeout: int = 30) -> MediaMetadata:
        """Extract media metadata and formats from a given URL."""
        clean_url = url.strip()
        if not clean_url:
            raise ValueError("URL cannot be empty")

        platform = detect_platform(clean_url)

        # 1. Fast check for direct image URLs or Pinterest pins
        if is_direct_image_url(clean_url) or "pinterest.com" in clean_url.lower() or "pin.it" in clean_url.lower():
            img_meta = ImageExtractor.extract_image_media(clean_url, timeout=timeout)
            if img_meta:
                return img_meta

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": timeout,
            "extract_flat": False,
            "noplaylist": False,
            "allow_unplayable_formats": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
                if not info:
                    raise RuntimeError("No media metadata was returned.")

                meta = YtDlpExtractor._build_metadata(clean_url, platform, info)
                if not meta.video_qualities and not meta.image_items:
                    img_meta = ImageExtractor.extract_image_media(clean_url, timeout=timeout)
                    if img_meta and img_meta.image_items:
                        return img_meta
                return meta
        except yt_dlp.utils.DownloadError as de:
            # Fallback to ImageExtractor before raising
            img_meta = ImageExtractor.extract_image_media(clean_url, timeout=timeout)
            if img_meta:
                return img_meta

            user_msg, detail = parse_extractor_error(str(de))
            logger.warning(f"Extract error for {clean_url}: {user_msg} ({detail})")
            raise RuntimeError(f"{user_msg}|||{detail}") from de
        except Exception as e:
            # Fallback to ImageExtractor before raising
            img_meta = ImageExtractor.extract_image_media(clean_url, timeout=timeout)
            if img_meta:
                return img_meta

            user_msg, detail = parse_extractor_error(str(e))
            logger.error(f"Unexpected error extracting {clean_url}: {e}")
            raise RuntimeError(f"{user_msg}|||{detail}") from e

    @staticmethod
    def _build_metadata(url: str, platform: str, info: Dict[str, Any]) -> MediaMetadata:
        # Check if carousel or multi-image entry
        entries = info.get("entries")
        first_entry = entries[0] if entries and len(entries) > 0 else info

        title = info.get("title") or first_entry.get("title") or "Not available"
        channel = (
            info.get("uploader")
            or first_entry.get("uploader")
            or info.get("channel")
            or first_entry.get("channel")
            or info.get("creator")
            or "Not available"
        )
        duration = info.get("duration") or first_entry.get("duration")
        upload_date_raw = info.get("upload_date") or first_entry.get("upload_date")  # YYYYMMDD
        if upload_date_raw and len(upload_date_raw) == 8:
            upload_date = f"{upload_date_raw[0:4]}-{upload_date_raw[4:6]}-{upload_date_raw[6:8]}"
        else:
            upload_date = info.get("release_date") or first_entry.get("release_date") or "Not available"

        language = info.get("language") or first_entry.get("language") or "Not available"
        if language != "Not available":
            language = language.upper()

        visibility = "Public"
        if info.get("availability") == "unlisted" or first_entry.get("availability") == "unlisted":
            visibility = "Unlisted"
        elif info.get("is_live") or first_entry.get("is_live"):
            visibility = "Live Stream"

        caption = info.get("description") or first_entry.get("description") or "Not available"
        view_count = info.get("view_count") or first_entry.get("view_count")
        like_count = info.get("like_count") or first_entry.get("like_count")
        thumbnail_url = info.get("thumbnail") or first_entry.get("thumbnail") or ""

        # Parse Video Qualities
        formats = first_entry.get("formats") or info.get("formats") or []
        video_qualities = YtDlpExtractor._parse_video_formats(formats, duration)

        # Parse Audio Qualities
        audio_qualities = YtDlpExtractor._parse_audio_formats(formats, duration)

        # Parse Thumbnail Qualities
        thumbnails_raw = first_entry.get("thumbnails") or info.get("thumbnails") or []
        thumbnail_qualities = YtDlpExtractor._parse_thumbnails(thumbnails_raw, thumbnail_url)

        # Parse Image Items (For photos, Instagram carousels, etc.)
        image_items: List[ImageItem] = []

        if entries and len(entries) > 0:
            for i, ent in enumerate(entries):
                img_url = ent.get("url") or ent.get("thumbnail") or ""
                if img_url:
                    image_items.append(
                        ImageItem(
                            url=img_url,
                            title=f"{title} - Photo {i + 1}",
                            resolution_str="High Resolution",
                            ext="jpg",
                        )
                    )
        elif not video_qualities and thumbnail_qualities:
            # Source contains photos/images without video
            for i, t in enumerate(thumbnail_qualities):
                image_items.append(
                    ImageItem(
                        url=t.url,
                        title=f"{title} - {t.label}",
                        resolution_str=t.resolution_str,
                        width=t.width,
                        height=t.height,
                        ext="jpg",
                    )
                )

        # Determine Media Type
        media_type = "Video"
        if not video_qualities and image_items:
            media_type = "Photo Gallery" if len(image_items) > 1 else "Image"
            # Clear audio qualities if this is strictly a photo/image post
            audio_qualities = []
        elif info.get("_type") == "url" or (info.get("vcodec") == "none" and audio_qualities):
            media_type = "Audio"

        return MediaMetadata(
            url=url,
            title=title,
            channel=channel,
            platform=platform,
            duration=duration,
            upload_date=upload_date,
            language=language,
            visibility=visibility,
            media_type=media_type,
            caption=caption,
            view_count=view_count,
            like_count=like_count,
            thumbnail_url=thumbnail_url,
            video_qualities=video_qualities,
            audio_qualities=audio_qualities,
            thumbnail_qualities=thumbnail_qualities,
            image_items=image_items,
        )

    @staticmethod
    def _parse_video_formats(formats: List[Dict[str, Any]], duration: Optional[float]) -> List[VideoQuality]:
        """Extract and deduplicate available video qualities dynamically."""
        seen_heights = {}

        for f in formats:
            # Skip storyboards, images, audio-only
            vcodec = f.get("vcodec", "none")
            if vcodec == "none" or f.get("protocol") == "mhtml":
                continue
            height = f.get("height")
            if not height or height < 144:
                continue

            width = f.get("width")
            fps = f.get("fps")
            acodec = f.get("acodec", "none")
            has_audio = acodec != "none"
            format_id = f.get("format_id", "")
            ext = f.get("ext", "mp4")

            # Filesize estimation
            filesize = f.get("filesize") or f.get("filesize_approx")
            if not filesize and duration and f.get("tbr"):
                # Total bitrate in kbps -> bytes
                filesize = int((f["tbr"] * 1024 / 8) * duration)

            resolution_label = f"{height}p"
            tbr = f.get("tbr") or 0.0

            # Favor H.264 (avc1) or higher bitrate when heights match
            is_better = False
            if height not in seen_heights:
                is_better = True
            else:
                prev = seen_heights[height]
                if tbr > (prev.get("tbr") or 0):
                    is_better = True
                elif "avc" in vcodec.lower() and "avc" not in prev.get("vcodec", "").lower():
                    is_better = True

            if is_better:
                seen_heights[height] = {
                    "resolution": resolution_label,
                    "width": width,
                    "height": height,
                    "fps": int(fps) if fps else None,
                    "vcodec": vcodec.split(".")[0] if vcodec else "H.264",
                    "acodec": "AAC" if has_audio else "Audio Merged",
                    "filesize_est": filesize,
                    "format_id": format_id,
                    "container": "MP4",
                    "has_audio": has_audio,
                    "needs_merge": not has_audio,
                    "bitrate": tbr,
                    "tbr": tbr,
                }

        # Convert to list sorted descending by height
        sorted_heights = sorted(seen_heights.keys(), reverse=True)
        qualities = []
        for h in sorted_heights:
            item = seen_heights[h]
            qualities.append(
                VideoQuality(
                    resolution=item["resolution"],
                    width=item["width"],
                    height=item["height"],
                    fps=item["fps"],
                    vcodec=item["vcodec"],
                    acodec=item["acodec"],
                    filesize_est=item["filesize_est"],
                    format_id=item["format_id"],
                    container=item["container"],
                    has_audio=item["has_audio"],
                    needs_merge=item["needs_merge"],
                    bitrate=item["bitrate"],
                )
            )
        return qualities

    @staticmethod
    def _parse_audio_formats(formats: List[Dict[str, Any]], duration: Optional[float]) -> List[AudioQuality]:
        """Provide sensible audio bitrates based on source availability."""
        # Find maximum available audio bitrate from source
        max_abr = 0.0
        for f in formats:
            if f.get("vcodec") == "none" or f.get("acodec") != "none":
                abr = f.get("abr") or f.get("tbr") or 0.0
                if abr > max_abr:
                    max_abr = abr

        # Standard sensible MP3 bitrates
        bitrates = [320, 256, 192, 128]
        result = []
        for b in bitrates:
            est_size = None
            if duration:
                # b kbps * duration / 8 = KB -> * 1024 bytes
                est_size = int((b * 1000 / 8) * duration)

            result.append(
                AudioQuality(
                    bitrate=f"{b} kbps",
                    bitrate_num=b,
                    filesize_est=est_size,
                    format="MP3",
                    duration=duration,
                )
            )
        return result

    @staticmethod
    def _parse_thumbnails(thumbnails_raw: List[Dict[str, Any]], default_url: str) -> List[ThumbnailQuality]:
        """Extract distinct quality levels for thumbnail."""
        if not thumbnails_raw and default_url:
            return [ThumbnailQuality(label="Original", url=default_url, resolution_str="High Resolution")]

        # Sort thumbnails by resolution (width * height) descending
        valid_thumbs = [t for t in thumbnails_raw if t.get("url")]
        valid_thumbs.sort(
            key=lambda t: (t.get("preference") or 0, (t.get("width") or 0) * (t.get("height") or 0)),
            reverse=True,
        )

        labels = ["Original", "High", "Medium", "Low"]
        result = []
        seen_urls = set()

        for i, t in enumerate(valid_thumbs):
            url = t.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            label = labels[len(result)] if len(result) < len(labels) else f"Option {len(result) + 1}"
            w = t.get("width")
            h = t.get("height")
            res_str = f"{w} × {h}" if w and h else "Available"

            result.append(
                ThumbnailQuality(
                    label=label,
                    url=url,
                    width=w,
                    height=h,
                    resolution_str=res_str,
                )
            )
            if len(result) >= 4:
                break

        if not result and default_url:
            result.append(ThumbnailQuality(label="Original", url=default_url, resolution_str="Available"))

        return result
