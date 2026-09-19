# MediaDrop — Universal Media Downloader

> **"One URL. Every Media."**

MediaDrop is a modern, production-quality desktop application built with **Python 3.12+** and **PySide6**. It accepts public media links from supported platforms and provides intelligent stream detection, high-resolution thumbnail extraction, audio conversion to MP3, and video stream merging using FFmpeg.

---

## Features

- **Universal Platform Support**:
  - **YouTube**: Videos, Shorts, MP3 audio, High-Res Thumbnails
  - **Instagram**: Reels, Posts, Carousels
  - **TikTok**: HD Videos & Audio tracks
  - **Facebook**: Public watch videos and clips
  - **X / Twitter**: Video tweets and media
  - **Pinterest**: Pins and visual media
  - **Generic Sites**: Any public media stream supported by yt-dlp

- **"What Do You Want To Download?" Selection**:
  - **Video (MP4)**: Detects exact native resolutions (2160p 4K, 1440p, 1080p, 720p, 480p, 360p) with FPS, codec, container, and estimated filesize. Automatically merges high-res video and best audio streams via FFmpeg.
  - **Audio (MP3)**: Dynamic bitrates (320 kbps, 256 kbps, 192 kbps, 128 kbps) with duration and size estimation.
  - **Images & Photos (Single & Galleries)**: Full-resolution photo downloading for Pinterest pins, Instagram photo posts & carousels, Twitter/X images, Unsplash, and direct image links. Select individual photos or batch-download all images in an album, with conversion to JPG, PNG, or WEBP via Pillow.
  - **Thumbnails**: Download detected thumbnails directly in Original, High, Medium, or Low quality, with instant conversion to JPG, PNG, or WEBP via Pillow.

- **Non-Blocking Architecture**:
  - URL analysis, network downloads, FFmpeg merging, and image conversions run entirely on dedicated background threads (`QThread`), keeping the UI responsive and fluid at 60 FPS.

- **Active Download Manager & Queue**:
  - Real-time progress bars, speed metrics, ETA calculations, downloaded/total byte counters.
  - Configurable concurrent downloads (default 3), automatic sequential queue processing.
  - Full control: Pause, Resume, Cancel, Retry, Open File, and Open Containing Folder.

- **Download History (SQLite)**:
  - Local SQLite database recording completed and past downloads.
  - Search by title or URL, filter by platform, one-click file opening, and re-download capability.

- **System & Clipboard Integration**:
  - Smart clipboard watcher: automatically alerts you with an action banner when a media URL is copied.
  - Drag-and-drop support: drag URLs or text files containing URLs directly into MediaDrop.

- **Safety & Windows Filename Sanitization**:
  - Forbidden Windows characters (`< > : " / \ | ? *`) are automatically sanitized.
  - Automatic collision resolution (`video (1).mp4`, `video (2).mp4`).
  - No arbitrary command execution or shell injection risks.

---

## Installation & Setup

### Prerequisites

1. **Python 3.12 or 3.13** installed on your system.
2. **FFmpeg** (v5.0+ recommended; FFmpeg 8.x fully supported).
   - If you do not have FFmpeg, install it via Windows Package Manager:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - MediaDrop automatically locates FFmpeg in PATH and standard installation paths. You can also specify a custom path in Settings.

### Step 1: Clone or Navigate to the Repository

```powershell
cd "d:\Work\Coding\Tech and Digital Skills\AI & ML\Python\carzy project idea\MediaDrop"
```

### Step 2: Install Python Dependencies

```powershell
pip install -r requirements.txt
```

---

## Running MediaDrop

Launch the application directly:

```powershell
python main.py
```

On first launch, MediaDrop will present a welcome wizard to verify your download folder and confirm that FFmpeg is detected.

---

## Packaging as Windows Standalone Executable (.exe)

You can package MediaDrop into a standalone Windows `.exe` using **PyInstaller**:

```powershell
pip install pyinstaller

pyinstaller --noconfirm --onedir --windowed `
  --name "MediaDrop" `
  --add-data "assets;assets" `
  main.py
```

The resulting executable will be located in `dist/MediaDrop/MediaDrop.exe`.

---

## Architecture

MediaDrop strictly adheres to separation of concerns:

```text
UI (PySide6)
  ├── Windows (MainWindow, Sidebar, Toasts)
  ├── Pages (HomePage, DownloadsPage, HistoryPage, SettingsPage)
  └── Widgets (MediaCard, FormatSelector, DownloadCard, IconButton)
        │
        ▼
Application Controller (MainController)
  ├── Queue Management & Concurrency Control
  └── Clipboard & Drag-and-Drop Watcher
        │
        ▼
Services Layer
  ├── MediaService (High-level Facade)
  ├── MetadataService (Parsing & Normalization)
  ├── DownloadService (yt-dlp Execution & Progress Hooks)
  ├── ConversionService (FFmpeg Remuxing & Transcoding)
  └── ThumbnailService (Pillow Conversion & Caching)
        │
        ▼
Storage & Engine
  ├── SQLite Database (History & State)
  ├── Configuration Manager (config.json)
  ├── FFmpeg Engine (Audio Extraction & Stream Merging)
  └── Local File System (Safe Windows Filenames & Collision Resolution)
```

---

## Troubleshooting

- **"FFmpeg missing" warning**:
  Ensure FFmpeg is installed and accessible in your system PATH, or navigate to **Settings** -> **FFmpeg Executable Path** and click **Browse** to select your `ffmpeg.exe`.
- **"Unable to access media"**:
  Verify your internet connection and ensure the target media is public and not restricted by login, geoblocking, or DRM.
- **Viewing Technical Logs**:
  Click **View Details** on any error dialog, or open `logs/mediadrop.log` in the application directory.

---

## Legal & Responsible Use Notice

MediaDrop is designed strictly for downloading public, non-DRM media that the user has legitimate permission and right to download. MediaDrop does not bypass DRM, encryption, authentication walls, paywalls, or private-content restrictions. Users are responsible for complying with applicable laws and the terms of service of each respective content platform.
