"""Web & platform image extractor for Pinterest, Instagram, Twitter/X, and direct images."""

import re
from io import BytesIO
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from PIL import Image
import requests

from app.database.models import ImageItem, MediaMetadata, ThumbnailQuality
from app.utils.logger import logger


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def is_direct_image_url(url: str) -> bool:
    """Check if URL points directly to an image by extension."""
    parsed = urlparse(url.lower().split("?")[0])
    path = parsed.path
    image_extensions = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg")
    return path.endswith(image_extensions)


def extract_meta_tag(html: str, property_names: List[str]) -> str:
    """Extract content from meta tag supporting content before or after property/name attribute."""
    for prop in property_names:
        escaped = re.escape(prop)
        # Match <meta property="prop" content="val">
        m1 = re.search(rf'<meta[^>]+(?:property|name)=["\']{escaped}["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m1:
            return m1.group(1).strip()
        # Match <meta content="val" property="prop">
        m2 = re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{escaped}["\']', html, re.I)
        if m2:
            return m2.group(1).strip()
    return ""


class ImageExtractor:
    """Extracts images and photos from Pinterest, social media posts, or direct image links."""

    @staticmethod
    def extract_image_media(url: str, timeout: int = 15) -> Optional[MediaMetadata]:
        """Attempt to extract image/photo metadata from a URL."""
        clean_url = url.strip()
        parsed = urlparse(clean_url)
        netloc = parsed.netloc.lower()

        # 1. Direct Image URL
        if is_direct_image_url(clean_url):
            return ImageExtractor._extract_direct_image(clean_url, timeout)

        # 2. Pinterest Pin
        if "pinterest.com" in netloc or "pin.it" in netloc:
            return ImageExtractor._extract_pinterest(clean_url, timeout)

        # 3. Generic Web Page Image / OpenGraph (Instagram, X, Flickr, Unsplash, Reddit, etc.)
        return ImageExtractor._extract_webpage_images(clean_url, timeout)

    @staticmethod
    def _extract_direct_image(url: str, timeout: int) -> Optional[MediaMetadata]:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, stream=True, timeout=timeout)
            if resp.status_code != 200:
                return None

            content_type = resp.headers.get("content-type", "").lower()
            if not ("image" in content_type or is_direct_image_url(url)):
                return None

            # Read first 128KB to inspect image dimensions via Pillow
            chunk = resp.raw.read(131072)
            w, h = None, None
            try:
                with Image.open(BytesIO(chunk)) as img:
                    w, h = img.size
            except Exception:
                pass

            filesize = None
            if "content-length" in resp.headers:
                try:
                    filesize = int(resp.headers["content-length"])
                except ValueError:
                    pass

            filename = url.split("?")[0].rstrip("/").split("/")[-1] or "Photo"
            platform_name = "Web Image"
            if "unsplash" in url:
                platform_name = "Unsplash"
            elif "pinimg" in url:
                platform_name = "Pinterest"

            res_str = f"{w} × {h}" if w and h else "Full Resolution"

            image_item = ImageItem(
                url=url,
                title=filename,
                resolution_str=res_str,
                width=w,
                height=h,
                filesize=filesize,
                ext="jpg",
            )

            thumb_item = ThumbnailQuality(
                label="Original",
                url=url,
                width=w,
                height=h,
                resolution_str=res_str,
            )

            return MediaMetadata(
                url=url,
                title=filename,
                channel=platform_name,
                platform=platform_name,
                duration=None,
                upload_date="Not available",
                language="Not available",
                visibility="Public",
                media_type="Image",
                caption="High-resolution direct media image",
                view_count=None,
                like_count=None,
                thumbnail_url=url,
                video_qualities=[],
                audio_qualities=[],
                thumbnail_qualities=[thumb_item],
                image_items=[image_item],
            )
        except Exception as e:
            logger.warning(f"Failed to extract direct image from {url}: {e}")
            return None

    @staticmethod
    def _extract_pinterest(url: str, timeout: int) -> Optional[MediaMetadata]:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=timeout)
            if resp.status_code != 200:
                return None

            html = resp.text

            # 1. Extract Title
            title = extract_meta_tag(html, ["og:title", "twitter:title"])
            if not title:
                t_match = re.search(r'<title>([^<]+)</title>', html, re.I)
                title = t_match.group(1).strip() if t_match else "Pinterest Pin"
            # Clean Pinterest title suffix like " | Pinterest"
            title = re.sub(r'\s*\|\s*Pinterest.*$', '', title, flags=re.I)

            # 2. Extract Description / Caption
            caption = extract_meta_tag(html, ["og:description", "description", "twitter:description"])
            if not caption:
                caption = "Not available"

            # 3. Extract the EXACT Pin Image (NEVER match arbitrary pinimg on page!)
            primary_img = extract_meta_tag(html, ["og:image", "twitter:image:src", "twitter:image"])
            if not primary_img:
                link_img = re.search(r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
                if link_img:
                    primary_img = link_img.group(1).strip()

            if not primary_img:
                return None

            # Upgrade to full original uncompressed resolution!
            orig_url = re.sub(r'/(?:236x|474x|564x|736x)/', '/originals/', primary_img)

            image_item = ImageItem(
                url=orig_url,
                title=f"{title}",
                resolution_str="Original HD",
                ext="jpg",
            )
            thumb_item = ThumbnailQuality(
                label="Original HD",
                url=orig_url,
                resolution_str="Original HD",
            )

            return MediaMetadata(
                url=url,
                title=title,
                channel="Pinterest",
                platform="Pinterest",
                duration=None,
                upload_date="Not available",
                language="Not available",
                visibility="Public",
                media_type="Image",
                caption=caption,
                view_count=None,
                like_count=None,
                thumbnail_url=orig_url,
                video_qualities=[],
                audio_qualities=[],
                thumbnail_qualities=[thumb_item],
                image_items=[image_item],
            )
        except Exception as e:
            logger.warning(f"Failed to extract Pinterest pin from {url}: {e}")
            return None

    @staticmethod
    def _extract_webpage_images(url: str, timeout: int) -> Optional[MediaMetadata]:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=timeout)
            if resp.status_code != 200:
                return None

            ctype = resp.headers.get("content-type", "").lower()
            if "image" in ctype:
                return ImageExtractor._extract_direct_image(resp.url, timeout)

            html = resp.text

            # Extract title
            title = extract_meta_tag(html, ["og:title", "twitter:title"])
            if not title:
                t_match = re.search(r'<title>([^<]+)</title>', html, re.I)
                title = t_match.group(1).strip() if t_match else "Web Media"

            # Extract platform
            site_name = extract_meta_tag(html, ["og:site_name"])
            platform = site_name if site_name else urlparse(url).netloc.split(".")[-2].capitalize()

            # Extract caption
            caption = extract_meta_tag(html, ["og:description", "description", "twitter:description"])
            if not caption:
                caption = "Not available"

            # Extract primary image
            img_url = extract_meta_tag(html, ["og:image", "twitter:image:src", "twitter:image"])
            if not img_url:
                link_img = re.search(r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
                if link_img:
                    img_url = link_img.group(1).strip()

            if not img_url or not img_url.startswith("http"):
                return None

            image_item = ImageItem(
                url=img_url,
                title=f"{title}",
                resolution_str="High Resolution",
                ext="jpg",
            )
            thumb_item = ThumbnailQuality(
                label="Original",
                url=img_url,
                resolution_str="High Resolution",
            )

            return MediaMetadata(
                url=url,
                title=title,
                channel=platform,
                platform=platform,
                duration=None,
                upload_date="Not available",
                language="Not available",
                visibility="Public",
                media_type="Image",
                caption=caption,
                view_count=None,
                like_count=None,
                thumbnail_url=img_url,
                video_qualities=[],
                audio_qualities=[],
                thumbnail_qualities=[thumb_item],
                image_items=[image_item],
            )
        except Exception as e:
            logger.warning(f"Failed to extract webpage images from {url}: {e}")
            return None

image_extractor = ImageExtractor()
