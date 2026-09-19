"""Download execution service using yt-dlp and FFmpeg."""

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yt_dlp

from app.database.models import DownloadItem
from app.extractors.yt_dlp_extractor import parse_extractor_error
from app.utils.config import config_manager
from app.utils.ffmpeg_utils import find_ffmpeg
from app.utils.file_utils import (
    format_bytes,
    format_duration,
    get_unique_filepath,
    sanitize_filename,
)
from app.utils.logger import logger


class DownloadCancelledException(Exception):
    """Raised when user cancels a download in progress."""
    pass


class DownloadService:
    """Manages execution of media downloads using yt-dlp."""

    @staticmethod
    def execute_download(
        task: DownloadItem,
        output_dir: Path,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        is_cancelled_func: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """Download video or audio using yt-dlp with progress & status hooks."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Detect FFmpeg
        custom_ffmpeg = config_manager.get("ffmpeg_path")
        ffmpeg_exe = find_ffmpeg(custom_ffmpeg)
        ffmpeg_location = str(ffmpeg_exe.parent) if ffmpeg_exe else None

        # Determine filename and extension
        fmt_type = task.format_type.lower()
        quality_str = sanitize_filename(task.quality)
        clean_title = sanitize_filename(task.title)
        
        if fmt_type == "audio":
            ext = "mp3"
            template_filename = f"{clean_title} [{quality_str}].%(ext)s"
        else:
            ext = "mp4"
            template_filename = f"{clean_title} [{quality_str}].%(ext)s"

        outtmpl = str(output_dir / template_filename)

        # yt-dlp options
        ydl_opts: Dict[str, Any] = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "overwrites": False,
        }

        if ffmpeg_location:
            ydl_opts["ffmpeg_location"] = ffmpeg_location

        # Speed limit if configured
        speed_limit = config_manager.get("speed_limit_kbs", 0)
        if speed_limit > 0:
            ydl_opts["ratelimit"] = speed_limit * 1024

        # Network timeout and retries
        ydl_opts["socket_timeout"] = config_manager.get("network_timeout", 30)
        ydl_opts["retries"] = config_manager.get("retry_count", 3)

        # Format specifics
        if fmt_type == "audio":
            bitrate_match = task.quality.split()[0] if task.quality else "320"
            try:
                bitrate_num = int(bitrate_match)
            except ValueError:
                bitrate_num = 320

            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(bitrate_num),
                }
            ]
        else:
            # Video
            # If specific format_id was passed, try it + bestaudio, merging into mp4
            format_id = task.selected_format_id
            if format_id:
                ydl_opts["format"] = f"{format_id}+bestaudio/best"
            else:
                # Fallback to height matching or best
                ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

            ydl_opts["merge_output_format"] = "mp4"

        # Hooks
        final_file_path: list[str] = []

        def ytdl_progress_hook(d: Dict[str, Any]):
            if is_cancelled_func and is_cancelled_func():
                raise DownloadCancelledException("Download cancelled by user")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed_raw = d.get("speed") or 0
                eta_raw = d.get("eta") or 0

                pct = (downloaded / total * 100.0) if total > 0 else 0.0
                speed_str = f"{format_bytes(speed_raw)}/s" if speed_raw else "0 B/s"
                eta_str = f"ETA {format_duration(eta_raw)}" if eta_raw else "--:--"

                if progress_callback:
                    progress_callback({
                        "status": "Downloading",
                        "progress": pct,
                        "downloaded_bytes": downloaded,
                        "total_bytes": total,
                        "speed": speed_str,
                        "eta": eta_str,
                    })

            elif status == "finished":
                filename = d.get("filename")
                if filename:
                    final_file_path.append(filename)
                if progress_callback:
                    progress_callback({
                        "status": "Processing",
                        "progress": 99.0,
                    })

        def ytdl_postprocessor_hook(d: Dict[str, Any]):
            if is_cancelled_func and is_cancelled_func():
                raise DownloadCancelledException("Download cancelled by user")

            status = d.get("status")
            pp = d.get("postprocessor", "")

            if status == "started":
                state = "Merging" if "Merger" in pp else "Converting" if "ExtractAudio" in pp else "Processing"
                if status_callback:
                    status_callback(state)
            elif status == "finished":
                pass

        ydl_opts["progress_hooks"] = [ytdl_progress_hook]
        ydl_opts["postprocessor_hooks"] = [ytdl_postprocessor_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(task.url, download=True)
                if info:
                    requested_downloads = info.get("requested_downloads")
                    if requested_downloads and len(requested_downloads) > 0:
                        file_candidate = requested_downloads[0].get("filepath")
                        if file_candidate and Path(file_candidate).exists():
                            return Path(file_candidate)

                    # Check expected filename from info
                    expected = ydl.prepare_filename(info)
                    p_expected = Path(expected)
                    # If converted to mp3 or mp4, check replacement extension
                    if fmt_type == "audio":
                        p_mp3 = p_expected.with_suffix(".mp3")
                        if p_mp3.exists():
                            return p_mp3
                    else:
                        p_mp4 = p_expected.with_suffix(".mp4")
                        if p_mp4.exists():
                            return p_mp4

                    if p_expected.exists():
                        return p_expected

                # Check final_file_path from hook
                if final_file_path:
                    fp = Path(final_file_path[-1])
                    if fmt_type == "audio":
                        fp_mp3 = fp.with_suffix(".mp3")
                        if fp_mp3.exists():
                            return fp_mp3
                    if fp.exists():
                        return fp

                # If still not found, search in output directory for matching pattern
                matches = list(output_dir.glob(f"{clean_title}*"))
                if matches:
                    return matches[0]

                raise RuntimeError("Download completed but destination file was not located.")

        except DownloadCancelledException:
            logger.info(f"Download cancelled for {task.title}")
            # Clean up partial files
            for part in output_dir.glob(f"{clean_title}*"):
                if part.suffix in [".part", ".ytdl"]:
                    try:
                        part.unlink()
                    except Exception:
                        pass
            raise
        except yt_dlp.utils.DownloadError as de:
            user_msg, detail = parse_extractor_error(str(de))
            logger.error(f"Download error: {user_msg} ({detail})")
            raise RuntimeError(f"{user_msg}|||{detail}") from de
        except Exception as e:
            user_msg, detail = parse_extractor_error(str(e))
            logger.error(f"Unexpected download error: {e}")
            raise RuntimeError(f"{user_msg}|||{detail}") from e
