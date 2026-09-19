#!/usr/bin/env python3
"""
Video Audio-Track Extractor for Windows
Extracts all audio tracks from a video file and ensures every track matches the exact
video playback duration and 0-normalized timeline for seamless compatibility with
YouTube Studio's multi-language audio track feature.

Key features:
- Detects exact video duration using FFprobe (stream, container, tags, and packet timing).
- Transcodes Opus audio to broadcast-standard WAV PCM (16-bit, 48000 Hz, stereo).
- Normalizes audio start timestamp to 0.000 (correcting delays and negative offsets).
- Trims or pads audio with silence to match exact video duration.
- Post-extraction FFprobe verification with automatic correction if length differs.
- Preserves all metadata, language names, track indexing, and collision-safe naming.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure Windows terminal handles UTF-8 (e.g. checkmarks, arrows, unicode languages)
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Maximum allowed difference (in seconds) between video and audio duration for YouTube Studio
TOLERANCE_SECONDS = 0.050

# Mapping of audio codec names to standard standalone audio container extensions
CODEC_CONTAINER_MAP = {
    "aac": ".m4a",
    "alac": ".m4a",
    "mp3": ".mp3",
    "flac": ".flac",
    "opus": ".wav",  # Transcoded to WAV PCM (48kHz, 16-bit) for YouTube Studio compatibility
    "vorbis": ".ogg",
    "ac3": ".ac3",
    "eac3": ".eac3",
    "dts": ".dts",
    "truehd": ".truehd",
    "wavpack": ".wv",
    "wmav1": ".wma",
    "wmav2": ".wma",
    "wmapro": ".wma",
    "wmalossless": ".wma",
}

# Mapping common ISO 639 language codes to capitalized names
LANGUAGE_MAP = {
    "eng": "English", "en": "English",
    "hin": "Hindi", "hi": "Hindi",
    "guj": "Gujarati", "gu": "Gujarati",
    "jpn": "Japanese", "ja": "Japanese",
    "spa": "Spanish", "es": "Spanish",
    "fra": "French", "fre": "French", "fr": "French",
    "deu": "German", "ger": "German", "de": "German",
    "ita": "Italian", "it": "Italian",
    "rus": "Russian", "ru": "Russian",
    "kor": "Korean", "ko": "Korean",
    "chi": "Chinese", "zho": "Chinese", "zh": "Chinese",
    "tam": "Tamil", "ta": "Tamil",
    "tel": "Telugu", "te": "Telugu",
    "ben": "Bengali", "bn": "Bengali",
    "mar": "Marathi", "mr": "Marathi",
    "pan": "Punjabi", "pa": "Punjabi",
    "mal": "Malayalam", "ml": "Malayalam",
    "kan": "Kannada", "kn": "Kannada",
    "urd": "Urdu", "ur": "Urdu",
    "por": "Portuguese", "pt": "Portuguese",
    "ara": "Arabic", "ar": "Arabic",
    "vie": "Vietnamese", "vi": "Vietnamese",
    "tha": "Thai", "th": "Thai",
    "ind": "Indonesian", "id": "Indonesian",
    "tur": "Turkish", "tr": "Turkish",
    "pol": "Polish", "pl": "Polish",
    "dut": "Dutch", "nld": "Dutch", "nl": "Dutch",
    "swe": "Swedish", "sv": "Swedish",
    "nor": "Norwegian", "no": "Norwegian",
    "dan": "Danish", "da": "Danish",
    "fin": "Finnish", "fi": "Finnish",
    "ell": "Greek", "el": "Greek",
    "heb": "Hebrew", "he": "Hebrew",
    "hun": "Hungarian", "hu": "Hungarian",
    "ces": "Czech", "cze": "Czech", "cs": "Czech",
    "ron": "Romanian", "rum": "Romanian", "ro": "Romanian",
    "ukr": "Ukrainian", "uk": "Ukrainian",
}


def check_dependencies() -> bool:
    """Check if ffmpeg and ffprobe are available in the system PATH."""
    missing = []
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    if not shutil.which("ffprobe"):
        missing.append("ffprobe")

    if missing:
        print("\n" + "=" * 60)
        print(" [ERROR] Required tool(s) not found in system PATH:")
        for tool in missing:
            print(f"   - {tool}")
        print("=" * 60)
        print("\nHow to install FFmpeg on Windows:")
        print("  Option 1 (Recommended - Windows Package Manager):")
        print("    Open PowerShell / Terminal and run:")
        print("      winget install Gyan.FFmpeg")
        print("\n  Option 2 (Using Chocolatey or Scoop):")
        print("      choco install ffmpeg   OR   scoop install ffmpeg")
        print("\n  Option 3 (Manual Download):")
        print("    1. Download the release build from: https://www.gyan.dev/ffmpeg/builds/")
        print("    2. Extract the archive (e.g. to C:\\ffmpeg).")
        print("    3. Add the 'bin' folder (e.g. C:\\ffmpeg\\bin) to your Windows PATH environment variable.")
        print("    4. Restart your terminal.")
        print("=" * 60 + "\n")
        return False
    return True


def sanitize_filename_part(text: str) -> str:
    """Remove or replace characters not allowed in Windows filenames."""
    sanitized = re.sub(r'[\\/*?:"<>|]', "", text)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized


def parse_duration_string(val) -> float | None:
    """
    Parse a duration string into seconds (float).
    Handles raw numeric strings ("5535.5"), HH:MM:SS, HH:MM:SS.mmm, or float values.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else 0.0

    val_str = str(val).strip()
    if not val_str:
        return None

    # Plain float/int check
    try:
        sec = float(val_str)
        return sec
    except ValueError:
        pass

    # Check HH:MM:SS or HH:MM:SS.mmm
    parts = val_str.split(":")
    if len(parts) == 3:
        try:
            h = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return h * 3600.0 + m * 60.0 + s
        except ValueError:
            pass
    elif len(parts) == 2:
        try:
            m = float(parts[0])
            s = float(parts[1])
            return m * 60.0 + s
        except ValueError:
            pass

    return None


def format_seconds_to_timestamp(seconds: float) -> str:
    """Format seconds into standard HH:MM:SS.mmm string."""
    if seconds is None:
        return "00:00:00.000"
    sign = "-" if seconds < 0 else ""
    sec_abs = abs(seconds)
    hours = int(sec_abs // 3600)
    minutes = int((sec_abs % 3600) // 60)
    secs = sec_abs % 60
    return f"{sign}{hours:02d}:{minutes:02d}:{secs:06.3f}"


def get_exact_video_duration(video_path: Path, probe_data: dict) -> float:
    """
    Determine the most accurate, reliable video duration using FFprobe.
    Checks video stream duration, container format duration, Matroska tags,
    and frame count calculations to handle various container quirks.
    """
    streams = probe_data.get("streams", [])
    fmt = probe_data.get("format", {})

    video_streams = [
        s for s in streams
        if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
    ]

    candidates = []

    # 1. Video stream metadata
    for vs in video_streams:
        dur_str = vs.get("duration")
        if dur_str:
            dur = parse_duration_string(dur_str)
            if dur and dur > 0:
                st = parse_duration_string(vs.get("start_time")) or 0.0
                candidates.append(("video_stream_duration", dur + max(0.0, st)))

        # Tag DURATION (common in Matroska MKV)
        tags = vs.get("tags", {})
        for k, v in tags.items():
            if "DURATION" in k.upper():
                dur = parse_duration_string(v)
                if dur and dur > 0:
                    candidates.append(("video_stream_tag_duration", dur))
                    break

        # Calculate from nb_frames and frame rate
        nb_frames_str = vs.get("nb_frames")
        avg_fps_str = vs.get("avg_frame_rate") or vs.get("r_frame_rate")
        if nb_frames_str and avg_fps_str and "/" in avg_fps_str:
            try:
                num, den = map(float, avg_fps_str.split("/"))
                if num > 0 and den > 0:
                    fps = num / den
                    nb_frames = float(nb_frames_str)
                    if fps > 0 and nb_frames > 0:
                        calc_dur = nb_frames / fps
                        candidates.append(("video_stream_calc_duration", calc_dur))
            except (ValueError, ZeroDivisionError):
                pass

    # 2. Container format metadata
    fmt_dur_str = fmt.get("duration")
    if fmt_dur_str:
        dur = parse_duration_string(fmt_dur_str)
        if dur and dur > 0:
            candidates.append(("format_duration", dur))

    fmt_tags = fmt.get("tags", {})
    for k, v in fmt_tags.items():
        if "DURATION" in k.upper():
            dur = parse_duration_string(v)
            if dur and dur > 0:
                candidates.append(("format_tag_duration", dur))
                break

    # Prioritize video stream duration over general container duration if valid
    for name, dur in candidates:
        if "video_stream" in name and dur > 0:
            return dur

    if candidates:
        return candidates[0][1]

    # 3. Direct FFprobe fallback query if missing from probe data
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        dur = float(res.stdout.strip())
        if dur > 0:
            return dur
    except Exception:
        pass

    return 0.0


def get_audio_stream_metadata(stream: dict, format_data: dict) -> dict:
    """Extract audio stream duration, start_time, sample_rate, channels, and codec."""
    codec = stream.get("codec_name", "unknown")
    sample_rate = stream.get("sample_rate")
    channels = stream.get("channels")

    # Start time
    start_time = 0.0
    st_str = stream.get("start_time")
    if st_str:
        parsed_st = parse_duration_string(st_str)
        if parsed_st is not None:
            start_time = parsed_st

    # Duration
    dur = None
    if stream.get("duration"):
        dur = parse_duration_string(stream.get("duration"))
    if dur is None:
        for k, v in stream.get("tags", {}).items():
            if "DURATION" in k.upper():
                dur = parse_duration_string(v)
                if dur:
                    break
    if dur is None and format_data.get("duration"):
        dur = parse_duration_string(format_data.get("duration"))

    return {
        "codec": codec,
        "sample_rate": sample_rate,
        "channels": channels,
        "start_time": start_time,
        "duration": dur if dur is not None else 0.0,
    }


def get_container_extension(codec_name: str) -> str:
    """
    Determine the best standalone audio container extension for the codec.
    Opus audio is mapped to .wav (PCM 16-bit 48kHz stereo) for YouTube Studio compatibility.
    Defaults to .mka (Matroska Audio) for exotic or unknown formats.
    """
    codec_lower = (codec_name or "").lower()
    if codec_lower == "opus":
        return ".wav"
    if codec_lower.startswith("pcm_"):
        return ".wav"
    return CODEC_CONTAINER_MAP.get(codec_lower, ".mka")


def is_opus_codec(codec_name: str) -> bool:
    """Check if the audio codec is Opus."""
    return (codec_name or "").lower() == "opus"


def get_unique_path(directory: Path, filename: str) -> Path:
    """Ensure the target filename is unique in the directory without overwriting."""
    target = directory / filename
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = directory / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def inspect_video(video_path: Path):
    """
    Run ffprobe to inspect streams and format of the video file.
    Returns (probe_data, audio_streams, error_message).
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        return data, audio_streams, None
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip() or f"ffprobe exited with returncode {e.returncode}"
        return None, [], err
    except json.JSONDecodeError:
        return None, [], "Failed to parse ffprobe output as JSON."
    except Exception as e:
        return None, [], str(e)


def extract_tag(tags: dict, tag_name: str) -> str:
    """Retrieve tag value case-insensitively."""
    if not tags:
        return ""
    tag_name_lower = tag_name.lower()
    for k, v in tags.items():
        if k.lower() == tag_name_lower and v:
            return str(v).strip()
    return ""


def get_track_display_name(stream: dict) -> str:
    """Determine a human-friendly name or language for display."""
    tags = stream.get("tags", {})
    lang = extract_tag(tags, "language")
    title = extract_tag(tags, "title")

    resolved_lang = ""
    if lang and lang.lower() not in ("und", "unknown", "zxx"):
        resolved_lang = LANGUAGE_MAP.get(lang.lower(), lang.capitalize())

    if resolved_lang and title:
        if resolved_lang.lower() in title.lower():
            return title
        return f"{resolved_lang} - {title}"
    if resolved_lang:
        return resolved_lang
    if title:
        return title
    return f"Track {stream.get('index', '')}"


def build_track_filename_label(stream: dict) -> str:
    """Build the descriptive suffix (language/title) for the output filename."""
    tags = stream.get("tags", {})
    lang = extract_tag(tags, "language")
    title = extract_tag(tags, "title")

    resolved_lang = ""
    if lang and lang.lower() not in ("und", "unknown", "zxx"):
        resolved_lang = LANGUAGE_MAP.get(lang.lower(), lang.capitalize())

    parts = []
    if resolved_lang:
        parts.append(resolved_lang)
    if title:
        cleaned_title = sanitize_filename_part(title)
        if cleaned_title and (not resolved_lang or cleaned_title.lower() != resolved_lang.lower()):
            if resolved_lang and resolved_lang.lower() in cleaned_title.lower():
                parts = [cleaned_title]
            else:
                parts.append(cleaned_title)

    if parts:
        combined = "_".join(parts)
        return sanitize_filename_part(combined)
    return ""


def extract_single_audio_track(
    video_path: Path,
    stream_index: int,
    output_path: Path,
) -> tuple[bool, str]:
    """
    Extract a single audio track using stream-copy (-c:a copy).
    Returns (success: bool, error_message: str).
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(video_path),
        "-map", f"0:{stream_index}",
        "-c:a", "copy",
        "-vn",
        str(output_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            return True, ""
        return False, proc.stderr.strip() or f"ffmpeg exited with returncode {proc.returncode}"
    except Exception as e:
        return False, str(e)


def extract_and_conform_opus_to_wav(
    video_path: Path,
    stream_index: int,
    output_path: Path,
    target_duration: float,
) -> tuple[bool, str]:
    """
    Extract Opus audio track and transcode to WAV PCM (16-bit, 48000 Hz, stereo)
    with exact duration matching target_duration (aligned to 0, padded with silence
    or trimmed as necessary).
    """
    # Build filter: resample & normalize first PTS to 0, pad silence to whole duration, trim excess
    filter_str = (
        f"aresample=async=1:first_pts=0,"
        f"apad=whole_dur={target_duration:.6f},"
        f"atrim=0:{target_duration:.6f},"
        f"asetpts=PTS-STARTPTS"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(video_path),
        "-map", f"0:{stream_index}",
        "-vn",
        "-af", filter_str,
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(output_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            return True, ""
        return False, proc.stderr.strip() or f"ffmpeg exited with returncode {proc.returncode}"
    except Exception as e:
        return False, str(e)


def correct_audio_track_duration(
    video_path: Path,
    stream_index: int,
    output_path: Path,
    target_duration: float,
    original_meta: dict,
) -> tuple[bool, Path, str]:
    """
    Re-encode and conform any audio track that failed duration matching
    to match the exact video duration (timeline starts at 0, padded/trimmed).
    Returns (success: bool, final_path: Path, error_message: str).
    """
    ext = output_path.suffix.lower()
    filter_str = (
        f"aresample=async=1:first_pts=0,"
        f"apad=whole_dur={target_duration:.6f},"
        f"atrim=0:{target_duration:.6f},"
        f"asetpts=PTS-STARTPTS"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(video_path),
        "-map", f"0:{stream_index}",
        "-vn",
        "-af", filter_str,
    ]

    # Select codec based on container format
    if ext == ".wav":
        cmd += ["-c:a", "pcm_s16le"]
        if original_meta.get("sample_rate"):
            cmd += ["-ar", str(original_meta["sample_rate"])]
        if original_meta.get("channels"):
            cmd += ["-ac", str(original_meta["channels"])]
    elif ext == ".m4a":
        cmd += ["-c:a", "aac", "-b:a", "320k"]
    elif ext == ".mp3":
        cmd += ["-c:a", "libmp3lame", "-b:a", "320k"]
    elif ext == ".flac":
        cmd += ["-c:a", "flac"]
    elif ext == ".ogg":
        cmd += ["-c:a", "libvorbis", "-q:a", "6"]
    elif ext == ".ac3":
        cmd += ["-c:a", "ac3", "-b:a", "640k"]
    elif ext == ".eac3":
        cmd += ["-c:a", "eac3", "-b:a", "640k"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "320k"]

    cmd.append(str(output_path))

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            return True, output_path, ""

        # Fallback to WAV PCM if container-specific encoding failed
        if ext != ".wav":
            wav_path = output_path.with_suffix(".wav")
            wav_cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(video_path),
                "-map", f"0:{stream_index}",
                "-vn",
                "-af", filter_str,
                "-c:a", "pcm_s16le",
                "-ar", "48000",
                "-ac", "2",
                str(wav_path),
            ]
            fallback_proc = subprocess.run(
                wav_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if fallback_proc.returncode == 0:
                if output_path.exists():
                    try:
                        output_path.unlink()
                    except OSError:
                        pass
                return True, wav_path, ""

        return False, output_path, proc.stderr.strip() or f"ffmpeg exited with returncode {proc.returncode}"
    except Exception as e:
        return False, output_path, str(e)


def verify_audio_file(
    audio_path: Path,
    video_duration: float,
    tolerance: float = TOLERANCE_SECONDS,
) -> tuple[bool, dict]:
    """
    Run FFprobe on the generated audio file to verify:
    - audio duration
    - video duration
    - duration difference
    - codec
    - sample rate
    - channels
    Returns (is_match: bool, details: dict).
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(audio_path),
    ]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        if not audio_streams:
            return False, {"error": "No audio stream found in generated file"}

        a_stream = audio_streams[0]
        fmt = data.get("format", {})

        # Determine audio duration
        audio_dur = None
        if a_stream.get("duration"):
            audio_dur = parse_duration_string(a_stream["duration"])
        if audio_dur is None and fmt.get("duration"):
            audio_dur = parse_duration_string(fmt["duration"])
        if audio_dur is None:
            audio_dur = (
                parse_duration_string(a_stream.get("tags", {}).get("DURATION"))
                or parse_duration_string(fmt.get("tags", {}).get("DURATION"))
            )

        if audio_dur is None:
            return False, {"error": "Could not determine audio duration"}

        diff = abs(audio_dur - video_duration)
        is_match = diff <= tolerance

        details = {
            "video_duration": video_duration,
            "audio_duration": audio_dur,
            "difference": diff,
            "codec": a_stream.get("codec_name", "unknown"),
            "sample_rate": a_stream.get("sample_rate", "unknown"),
            "channels": a_stream.get("channels", "unknown"),
            "is_match": is_match,
        }
        return is_match, details
    except Exception as e:
        return False, {"error": str(e)}


def print_verification_report(details: dict):
    """Print the formatted verification summary report."""
    v_dur = details.get("video_duration", 0.0)
    a_dur = details.get("audio_duration", 0.0)
    diff = details.get("difference", 0.0)
    codec = details.get("codec", "unknown")
    sr = details.get("sample_rate", "unknown")
    ch = details.get("channels", "unknown")
    is_match = details.get("is_match", False)

    print(f"       Codec          : {codec}")
    print(f"       Channels       : {ch}")
    print(f"       Sample rate    : {sr} Hz")
    print(f"       Video duration : {format_seconds_to_timestamp(v_dur)}")
    print(f"       Audio duration : {format_seconds_to_timestamp(a_dur)}")
    print(f"       Difference     : {diff:.3f} sec")
    if is_match:
        print("       Status         : \u2713 MATCH")
    else:
        print(f"       Status         : \u2717 MISMATCH (Tolerance: {TOLERANCE_SECONDS:.3f} sec)")


def process_video_extraction(raw_path: str):
    """Validate path, inspect audio streams, and extract/conform all tracks."""
    cleaned_path = raw_path.strip()
    if (cleaned_path.startswith('"') and cleaned_path.endswith('"')) or \
       (cleaned_path.startswith("'") and cleaned_path.endswith("'")):
        cleaned_path = cleaned_path[1:-1].strip()

    if not cleaned_path:
        print("\n[Error] No path entered.")
        return

    video_path = Path(cleaned_path)

    if not video_path.exists():
        print(f"\n[Error] File not found: {cleaned_path}")
        print("Please check that the path is correct and accessible.")
        return

    if video_path.is_dir():
        print(f"\n[Error] The specified path is a directory, not a video file: {cleaned_path}")
        return

    # Inspect media with ffprobe
    probe_data, audio_streams, probe_err = inspect_video(video_path)
    if probe_err:
        print(f"\n[Error] Could not inspect file with FFprobe: {probe_err}")
        return

    if not audio_streams:
        print(f"\n[Info] No audio tracks detected in '{video_path.name}'.")
        return

    # Determine exact video duration
    video_duration = get_exact_video_duration(video_path, probe_data)
    if video_duration <= 0.0:
        print(f"\n[Error] Could not determine video duration for '{video_path.name}'.")
        print("Audio tracks require an exact video length to conform for YouTube Studio.")
        return

    video_name = video_path.name
    video_dir = video_path.resolve().parent
    video_stem = video_path.stem
    total_tracks = len(audio_streams)

    print("\n" + "=" * 50)
    print("        VIDEO AUDIO-TRACK EXTRACTION")
    print("=" * 50)
    print(f"Video file     : {video_name}")
    print(f"Directory      : {video_dir}")
    print(f"Video duration : {format_seconds_to_timestamp(video_duration)} ({video_duration:.3f} sec)")
    print(f"Audio tracks   : {total_tracks}")
    print("=" * 50)

    successful_extractions = []
    failed_extractions = []

    for idx, stream in enumerate(audio_streams, start=1):
        stream_index = stream.get("index")
        codec_name = stream.get("codec_name", "unknown")
        display_name = get_track_display_name(stream)
        label = build_track_filename_label(stream)
        opus_track = is_opus_codec(codec_name)

        # Read audio stream specific properties
        meta = get_audio_stream_metadata(stream, probe_data.get("format", {}))
        ext = get_container_extension(codec_name)

        # Construct collision-safe filename
        track_tag = f"Audio_{idx:02d}"
        if label:
            filename = f"{video_stem}_{track_tag}_{label}{ext}"
        else:
            filename = f"{video_stem}_{track_tag}{ext}"

        output_path = get_unique_path(video_dir, filename)

        print(f"\n[{idx}/{total_tracks}] Processing: {display_name}")
        print(f"       Source Codec   : {codec_name}")
        print(f"       Channels       : {meta.get('channels') or 'N/A'}")
        print(f"       Sample Rate    : {meta.get('sample_rate') or 'N/A'} Hz")
        print(f"       Start Time     : {meta.get('start_time', 0.0):.3f} sec")
        print(f"       Stream Dur     : {format_seconds_to_timestamp(meta.get('duration', 0.0))}")
        print(f"       Target (Video) : {format_seconds_to_timestamp(video_duration)}")
        print(f"       Output Path    : {output_path.name}")

        success = False
        err = ""

        if opus_track:
            # Opus -> WAV PCM (48000 Hz, 16-bit, 2-channel) with pad/trim timeline conformance
            print(f"       Action         : Transcoding Opus \u2192 WAV PCM (48kHz, 16-bit stereo, length-conformed)...", end="", flush=True)
            success, err = extract_and_conform_opus_to_wav(video_path, stream_index, output_path, video_duration)
            if success:
                print(" done.")
            else:
                print(" FAILED.")
                print(f"       Error          : {err}")
        else:
            # Non-Opus: Try stream-copy first
            print(f"       Action         : Extracting with stream-copy (-c:a copy)...", end="", flush=True)
            success, err = extract_single_audio_track(video_path, stream_index, output_path)

            # If direct container copy failed, fallback to universal .mka container
            if not success and ext != ".mka":
                fallback_filename = output_path.stem + ".mka"
                fallback_path = get_unique_path(video_dir, fallback_filename)
                fallback_success, fallback_err = extract_single_audio_track(video_path, stream_index, fallback_path)
                if fallback_success:
                    if output_path.exists():
                        try:
                            output_path.unlink()
                        except OSError:
                            pass
                    output_path = fallback_path
                    success = True
                    err = ""
                else:
                    err = f"{err} (Fallback to .mka also failed: {fallback_err})"

            if success:
                print(" done.")
            else:
                print(" FAILED.")
                print(f"       Error          : {err}")

        # Post-extraction verification and automatic correction
        if success and output_path.exists():
            print("       Verification   : Running FFprobe verification...")
            is_match, details = verify_audio_file(output_path, video_duration, TOLERANCE_SECONDS)

            if is_match:
                print_verification_report(details)
                successful_extractions.append(output_path.name)
            else:
                print_verification_report(details)
                print(f"       Notice         : Audio duration differs from video duration by {details.get('difference', 0.0):.3f} sec.")
                print("       Auto-Correct   : Synchronizing timeline to 0 and padding/trimming to match video length...", end="", flush=True)

                corr_success, final_path, corr_err = correct_audio_track_duration(
                    video_path,
                    stream_index,
                    output_path,
                    video_duration,
                    meta,
                )

                if corr_success and final_path.exists():
                    output_path = final_path
                    print(" done.")
                    print("       Re-Verifying   : Running FFprobe verification on corrected file...")
                    re_match, re_details = verify_audio_file(output_path, video_duration, TOLERANCE_SECONDS)
                    print_verification_report(re_details)
                    if re_match:
                        successful_extractions.append(output_path.name)
                    else:
                        print("       [Warning] Duration difference persists after correction.")
                        successful_extractions.append(output_path.name)
                else:
                    print(" FAILED.")
                    print(f"       Correction Err : {corr_err}")
                    failed_extractions.append((display_name, f"Duration mismatch and correction failed: {corr_err}"))
        else:
            failed_extractions.append((display_name, err))
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass

    print("\n" + "=" * 50)
    if successful_extractions and not failed_extractions:
        print("Extraction & verification completed successfully!")
        print("\nAll generated audio tracks match the video length for YouTube Studio:")
        for name in successful_extractions:
            print(f"  + {name}")
    elif successful_extractions and failed_extractions:
        print(f"Extraction completed with {len(failed_extractions)} failure(s).")
        print("\nSuccessfully conformed files:")
        for name in successful_extractions:
            print(f"  + {name}")
        print("\nFailed tracks:")
        for name, reason in failed_extractions:
            print(f"  - {name}: {reason}")
    else:
        print("Extraction failed for all audio tracks.")
    print("=" * 50)


def main():
    """Main application loop displaying the interactive terminal menu."""
    if not check_dependencies():
        input("\nPress Enter to exit...")
        sys.exit(1)

    while True:
        print("\n====================================")
        print("     VIDEO AUDIO TRACK EXTRACTOR    ")
        print("====================================")
        print("\n1. Extract Audio Tracks (YouTube Studio Length-Conformed)")
        print("2. Exit\n")

        choice = input("Enter your choice: ").strip()

        if choice == "1":
            print("\n" + "=" * 36)
            print("Enter or paste the full video file path:")
            print("(Example: D:\\Movies\\My Movie.mkv or \"C:\\Videos\\clip.mp4\")")
            video_input = input("\nPath: ")
            process_video_extraction(video_input)
        elif choice == "2":
            print("\nExiting...")
            print("Goodbye!\n")
            break
        else:
            print("\n[Invalid choice] Please enter 1 or 2.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting...")
        sys.exit(0)
