"""Thumbnail extraction, preview caching, and format conversion via Pillow."""

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image
import requests

from app.utils.file_utils import get_unique_filepath, sanitize_filename
from app.utils.logger import logger


class ThumbnailService:
    """Manages downloading, previewing, and converting thumbnails."""

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path(__file__).resolve().parent.parent.parent / "downloads" / ".thumbnails"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_preview_image(self, url: str) -> Optional[Path]:
        """Download thumbnail to local cache and return cached Path for fast display."""
        if not url:
            return None

        # Check hash
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{url_hash}.img"

        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path

        browser_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

        try:
            resp = requests.get(url, timeout=15, headers=browser_headers)
            if resp.status_code == 200 and resp.content:
                cache_path.write_bytes(resp.content)
                return cache_path
        except Exception as e:
            logger.warning(f"Failed to fetch thumbnail preview from {url}: {e}")

        return None

    def download_thumbnail(
        self,
        url: str,
        output_dir: Path,
        base_name: str,
        target_format: str = "JPG",
        suffix_tag: str = "",
    ) -> Path:
        """Download thumbnail or image and convert to target_format (JPG, PNG, WEBP)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(base_name)
        fmt = target_format.upper()
        ext = ".jpg" if fmt in ("JPG", "JPEG") else f".{fmt.lower()}"

        tag = f" {suffix_tag.strip()}" if suffix_tag.strip() else ""
        target_file = get_unique_filepath(output_dir / f"{safe_name}{tag}{ext}")

        browser_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

        # Fetch image bytes
        resp = requests.get(url, timeout=30, headers=browser_headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to download image (HTTP {resp.status_code})")

        img_data = resp.content
        with Image.open(BytesIO(img_data)) as img:
            # Handle RGBA to RGB for JPEG
            if fmt in ("JPG", "JPEG"):
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    bg.save(target_file, "JPEG", quality=95)
                else:
                    img.convert("RGB").save(target_file, "JPEG", quality=95)
            elif fmt == "PNG":
                img.save(target_file, "PNG", optimize=True)
            elif fmt == "WEBP":
                img.save(target_file, "WEBP", quality=95)
            else:
                target_file.write_bytes(img_data)

        return target_file


thumbnail_service = ThumbnailService()
