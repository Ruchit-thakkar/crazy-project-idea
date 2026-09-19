"""FFmpeg detection, validation, and safe invocation."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


def find_ffmpeg(custom_path: str | None = None) -> Path | None:
    """Find FFmpeg executable from custom path, PATH, or common locations."""
    if custom_path and custom_path.strip():
        p = Path(custom_path.strip())
        if p.is_file() and os.access(p, os.X_OK):
            return p
        if p.is_dir():
            exe = p / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            if exe.is_file() and os.access(exe, os.X_OK):
                return exe

    # Check system PATH
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)

    # Common Windows paths (e.g. winget, chocolatey, scoop, local app data)
    common_windows_paths = [
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe")),
        Path(os.path.expandvars(r"%PROGRAMFILES%\ffmpeg\bin\ffmpeg.exe")),
        Path(os.path.expandvars(r"%PROGRAMFILES(X86)%\ffmpeg\bin\ffmpeg.exe")),
        Path(os.path.expandvars(r"%USERPROFILE%\scoop\shims\ffmpeg.exe")),
        Path(os.path.expandvars(r"%ALLUSERSPROFILE%\chocolatey\bin\ffmpeg.exe")),
    ]
    for candidate in common_windows_paths:
        if candidate.is_file():
            return candidate

    return None


def get_ffmpeg_version(ffmpeg_path: Path | str | None = None) -> Tuple[bool, str]:
    """Validate FFmpeg and return (is_available, version_string)."""
    if isinstance(ffmpeg_path, str):
        ffmpeg_path = Path(ffmpeg_path)
    
    if ffmpeg_path is None:
        ffmpeg_path = find_ffmpeg()

    if ffmpeg_path is None:
        return False, "FFmpeg not found"

    try:
        res = subprocess.run(
            [str(ffmpeg_path), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if res.returncode == 0:
            first_line = res.stdout.splitlines()[0] if res.stdout else "Available"
            # Extract concise version e.g. "8.1.1-full_build..." or "version 8.1.1"
            match = re.search(r"ffmpeg version ([^\s]+)", first_line)
            ver = match.group(1) if match else first_line
            return True, ver
        return False, "Failed to run FFmpeg"
    except Exception as e:
        return False, str(e)


def run_ffmpeg_command(
    args: list[str],
    ffmpeg_path: Path | str | None = None,
    timeout: int = 300,
) -> Tuple[bool, str]:
    """Safely run FFmpeg command with argument list (preventing shell injection)."""
    if ffmpeg_path is None:
        found = find_ffmpeg()
        if not found:
            return False, "FFmpeg executable not found"
        cmd = [str(found)] + args
    else:
        cmd = [str(ffmpeg_path)] + args

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if proc.returncode == 0:
            return True, proc.stdout
        return False, proc.stderr or proc.stdout
    except Exception as e:
        return False, str(e)
