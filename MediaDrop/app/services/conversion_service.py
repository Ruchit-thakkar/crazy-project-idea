"""FFmpeg conversion and media remuxing service."""

from pathlib import Path
from typing import Optional, Tuple

from app.utils.config import config_manager
from app.utils.ffmpeg_utils import find_ffmpeg, run_ffmpeg_command
from app.utils.logger import logger


class ConversionService:
    """Manages audio conversion and media stream merging via FFmpeg."""

    def __init__(self):
        pass

    def get_ffmpeg_executable(self) -> Optional[Path]:
        custom = config_manager.get("ffmpeg_path")
        return find_ffmpeg(custom)

    def convert_audio_to_mp3(
        self,
        input_file: Path,
        output_file: Path,
        bitrate_k: int = 320,
    ) -> Tuple[bool, str]:
        """Convert input media to MP3 with specified bitrate."""
        ffmpeg_bin = self.get_ffmpeg_executable()
        if not ffmpeg_bin:
            return False, "FFmpeg executable not found"

        args = [
            "-y",
            "-i", str(input_file),
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", f"{bitrate_k}k",
            str(output_file),
        ]
        success, out = run_ffmpeg_command(args, ffmpeg_path=ffmpeg_bin)
        return success, out

    def merge_video_audio(
        self,
        video_file: Path,
        audio_file: Path,
        output_file: Path,
    ) -> Tuple[bool, str]:
        """Merge separate video and audio streams into MP4 container."""
        ffmpeg_bin = self.get_ffmpeg_executable()
        if not ffmpeg_bin:
            return False, "FFmpeg executable not found"

        args = [
            "-y",
            "-i", str(video_file),
            "-i", str(audio_file),
            "-c:v", "copy",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_file),
        ]
        success, out = run_ffmpeg_command(args, ffmpeg_path=ffmpeg_bin)
        return success, out


conversion_service = ConversionService()
