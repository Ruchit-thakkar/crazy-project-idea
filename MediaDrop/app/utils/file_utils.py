"""File, path, and formatting utilities."""

import os
import re
import subprocess
import sys
from pathlib import Path


# Windows forbidden filename characters: < > : " / \ | ? *
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Remove forbidden characters and trim to a safe length."""
    if not name:
        return "unnamed_media"
    
    # Replace invalid chars with hyphen or underscore
    clean_name = _INVALID_FILENAME_CHARS.sub("_", name)
    # Strip whitespace, dots, and trailing spaces that Windows dislikes
    clean_name = clean_name.strip(" .")
    # Collapse multiple underscores
    clean_name = re.sub(r"_+", "_", clean_name)
    
    if not clean_name:
        clean_name = "unnamed_media"
        
    return clean_name[:max_length].rstrip(" .")


def get_unique_filepath(target_path: Path) -> Path:
    """Return unique path by appending (1), (2), etc. if file already exists."""
    if not target_path.exists():
        return target_path

    parent = target_path.parent
    stem = target_path.stem
    suffix = target_path.suffix

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def format_bytes(num_bytes: float | int | None) -> str:
    """Format bytes into human-readable string (e.g. 14.5 MB)."""
    if num_bytes is None or num_bytes < 0:
        return "Unknown size"
    
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            if unit in ["B"]:
                return f"{int(num_bytes)} {unit}"
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def format_duration(seconds: float | int | None) -> str:
    """Format duration in seconds into HH:MM:SS or MM:SS."""
    if seconds is None or seconds < 0:
        return "Not available"
    
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_count(count: int | None) -> str:
    """Format numbers into short forms like 1.2M, 45K."""
    if count is None or count < 0:
        return "Not available"
    
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def open_file_in_os(file_path: str | Path) -> bool:
    """Open a file using default system viewer."""
    path = Path(file_path)
    if not path.exists():
        return False
    
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except Exception:
        return False


def open_folder_in_os(file_path: str | Path) -> bool:
    """Open enclosing directory and highlight file if on Windows."""
    path = Path(file_path)
    try:
        if sys.platform == "win32":
            if path.exists():
                subprocess.run(["explorer", f"/select,{path.resolve()}"], check=False)
            else:
                folder = path.parent if path.suffix else path
                folder.mkdir(parents=True, exist_ok=True)
                subprocess.run(["explorer", str(folder.resolve())], check=False)
        elif sys.platform == "darwin":
            folder = path.parent if path.is_file() else path
            subprocess.run(["open", str(folder)], check=False)
        else:
            folder = path.parent if path.is_file() else path
            subprocess.run(["xdg-open", str(folder)], check=False)
        return True
    except Exception:
        return False
