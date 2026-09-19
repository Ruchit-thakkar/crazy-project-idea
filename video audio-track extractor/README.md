# Video Audio-Track Extractor (Windows)

A lightweight, terminal-based Python application for Windows to extract **ALL** audio tracks from any video file without re-encoding, preserving 100% of the original audio quality.

---

## Features

- **Extracts All Audio Tracks**: Discovers and extracts every audio stream present in the video file (e.g., English, Hindi, Gujarati, Japanese, commentary, etc.), not just the default track.
- **YouTube Studio Audio-Track Conformance**: Ensures every extracted audio track matches the exact duration of the source video timeline and starts at timestamp 0.000, avoiding YouTube Studio's *"Processing failed. Audio tracks must match video length"* error.
- **Timestamp Offset Correction & Trimming/Padding**:
  - Automatically pads the end with silence if an audio track is shorter than the video.
  - Trims excess audio if an audio track is longer than the video.
  - Synchronizes non-zero or negative start times to start cleanly at 0.
- **Post-Extraction FFprobe Verification**: Verifies audio duration against video duration. If any difference exceeds the tolerance, automatically corrects the file.
- **Opus &rarr; Broadcast WAV PCM**: Transcodes Opus streams directly into high-fidelity uncompressed WAV PCM (`-c:a pcm_s16le -ar 48000 -ac 2`) conformed to the video length.
- **Zero Loss Quality (Stream-Copy)**: Uses FFmpeg stream copying (`-c:a copy`) when streams already match the video duration.
- **Automatic Output Format Matching**: Detects the original audio codec of each stream and selects the best native container:
  - AAC / ALAC &rarr; `.m4a`
  - MP3 &rarr; `.mp3`
  - FLAC &rarr; `.flac`
  - Opus &rarr; `.wav` (transcoded to WAV PCM 48kHz, 16-bit stereo)
  - Vorbis &rarr; `.ogg`
  - AC-3 / Dolby Digital &rarr; `.ac3`
  - E-AC-3 / Dolby Digital Plus &rarr; `.eac3`
  - DTS &rarr; `.dts`
  - TrueHD &rarr; `.truehd`
  - PCM / Uncompressed &rarr; `.wav`
  - Exotic / Unknown codecs &rarr; `.mka` (Matroska Audio, universal lossless container)
- **Safe Output Naming**:
  - Automatically saves extracted tracks in the exact same directory as the source video.
  - Formats filenames with track indices and language/title metadata (e.g., `Movie_Audio_01_English.m4a`, `Movie_Audio_02_Hindi.mp3`).
  - Collision-safe: automatically appends `(1)`, `(2)`, etc., to prevent overwriting existing files.
- **Robust Windows Path Handling**:
  - Works with any Windows drive (`C:\`, `D:\`, `E:\`, external drives, UNC network paths).
  - Handles paths containing spaces, parentheses, special characters, and pasted paths enclosed in quotes.
- **Looping Terminal UI**: Stay in the main menu to process multiple videos without restarting.

---

## Prerequisites

1. **Python 3.8+** (installed and added to PATH).
2. **FFmpeg & FFprobe** (installed and added to PATH).

### How to Install FFmpeg on Windows

If you do not have FFmpeg installed yet, use one of the following methods:

#### Method 1: Using Windows Package Manager (winget - Recommended)
Open PowerShell and run:
```powershell
winget install Gyan.FFmpeg
```

#### Method 2: Using Chocolatey or Scoop
```powershell
choco install ffmpeg
# or
scoop install ffmpeg
```

#### Method 3: Manual Installation
1. Download a release build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
2. Extract the folder (e.g., to `C:\ffmpeg`).
3. Add `C:\ffmpeg\bin` to your system's **PATH** environment variable.
4. Open a new terminal window to apply changes.

---

## How to Run

1. Open your terminal (PowerShell, Command Prompt, or Windows Terminal) in the project directory:
   ```powershell
   python audio_extractor.py
   ```

2. Select `1` from the menu:
   ```text
   ====================================
        VIDEO AUDIO TRACK EXTRACTOR    
   ====================================

   1. Extract Audio Tracks
   2. Exit

   Enter your choice: 1
   ```

3. Paste the full path to your video file (you can copy it from Windows File Explorer with **Shift + Right Click &rarr; Copy as path**).
4. The program will detect all audio streams and extract them automatically to the video's directory.
