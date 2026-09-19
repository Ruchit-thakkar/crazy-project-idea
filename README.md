# Crazy Project Ideas 🚀

A curated collection of practical, smart, and innovative desktop and AI-powered utility tools built with Python.

---

## 📂 Included Projects

### 1. [MediaDrop](./MediaDrop) — Smart Desktop Universal Downloader
A modern multi-platform desktop media downloader and stream extractor powered by `CustomTkinter` and `yt-dlp`.
- **Key Features**:
  - Download video/audio from YouTube, Instagram, Vimeo, and 1000+ supported sites.
  - Playlist processing, quality presets (Up to 4K / MP3 320kbps).
  - Native clipboard URL monitor and system tray quick-actions.
  - SQLite download history and dark/light UI themes.
- **Tech Stack**: Python, CustomTkinter, yt-dlp, SQLite.

---

### 2. [Background Removal Application](./Background%20Removal%20application) — AI Image Matte & Cutout Studio
An intuitive desktop software for instant, high-quality image background removal.
- **Key Features**:
  - Neural-network powered background subtraction (`rembg` / `u2net` / `birefnet`).
  - Batch processing workflow for multi-image cutout.
  - Export to transparent PNG or custom color backgrounds.
- **Tech Stack**: Python, PySide6 / PyQt, Rembg, ONNX Runtime.

---

### 3. [Video Audio-Track Extractor](./video%20audio-track%20extractor) — Batch Demuxing & Extraction Tool
A high-performance audio track extractor and converter for media files.
- **Key Features**:
  - Lossless stream copying and high-quality transcoding (MP3, WAV, AAC, FLAC).
  - Multi-stream identification (select commentary, foreign language tracks, etc.).
  - Batch conversion pipeline.
- **Tech Stack**: Python, FFmpeg, Tkinter / Custom GUI.

---

## 🛠️ General Setup & Requirements

Each project operates independently with its own requirements and dependencies.

### Prerequisites
- Python 3.10+ installed
- [FFmpeg](https://ffmpeg.org/) installed and available in your system PATH (required for MediaDrop & Audio Extractor)

### Getting Started with Any Project
Navigate into the respective project directory and set up a virtual environment:

```bash
# Clone the repository
git clone https://github.com/Ruchit-thakkar/crazy-project-idea.git
cd crazy-project-idea

# Pick a project (e.g., MediaDrop)
cd MediaDrop

# Install dependencies
pip install -r requirements.txt

# Launch application
python main.py
```

---

## 📄 License
This repository is licensed under the [MIT License](LICENSE).
