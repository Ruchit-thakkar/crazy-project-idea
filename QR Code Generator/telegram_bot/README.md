# 🤖 QR Code Generator Telegram Bot

An autonomous, 24/7 cloud-ready Telegram Bot that instantly generates crisp, high-resolution QR codes from text, website URLs, email addresses, phone numbers, and Unicode messages.

This service is packaged as an independent Python application inside the `telegram_bot/` directory, operating without launching or interfering with the existing desktop application.

---

## 🌟 Features

- **Universal QR Encoding**: Converts any valid text, web link (`http://`, `https://`), contact email (`mailto:` or standard address), phone number (`tel:` or digits), and notes into standard QR codes.
- **Full Unicode Support**: Flawlessly encodes emojis (🚀, 💡), international alphabets (Japanese, Chinese, Arabic, Cyrillic, Hindi, Spanish, etc.), and symbols.
- **Strict Privacy & Security**:
  - Zero data storage: user inputs are not saved to any database or local log.
  - Temporary PNG files are strictly deleted from disk immediately after being sent to Telegram.
  - Safe sanitization against oversized payloads (limit: 2,000 characters).
- **High-Quality Standards**:
  - Follows ISO/IEC 18004 standards.
  - Level M Error Correction (recovers up to 15% of corrupted or obscured data).
  - Quiet-zone margin of 4 blocks for guaranteed scannability across iOS and Android camera apps.
- **Interactive Telegram UI**:
  - Interactive `/start` menu with inline action buttons (`Generate QR Code`, `Help`, `About`).
  - `/help` command with formatting examples and usage instructions.
  - `/about` command detailing privacy and technical specifications.
  - Real-time photo upload indicator.
- **Autonomous Cloud-Ready Design**:
  - Uses long-polling architecture (no inbound ports, webhooks, or SSL certificates required).
  - Runs 24/7 on cloud platforms (e.g., Railway, Render, Fly.io, or VPS) as a background worker.

---

## 📋 System Requirements

- **Python**: 3.10, 3.11, 3.12, or 3.13
- **Pip**: Latest version recommended
- **Operating System**: Windows, Linux, or macOS

---

## 🚀 Quick Start & Local Setup

All commands below should be executed from the `telegram_bot` folder.

### 1. Navigate to the Bot Directory

```bash
cd telegram_bot
```

### 2. Create & Activate a Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows Command Prompt (cmd.exe):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Your Bot Token

Obtain a bot token from [@BotFather](https://t.me/BotFather) on Telegram. Set it securely as an environment variable in your terminal session:

> ⚠️ **Important:** Never hardcode your token into source files or commit token files to version control.

**Windows PowerShell:**
```powershell
$env:TELEGRAM_BOT_TOKEN="your_actual_bot_token_here"
```

**Windows Command Prompt:**
```cmd
set TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
```

**Linux / macOS:**
```bash
export TELEGRAM_BOT_TOKEN="your_actual_bot_token_here"
```

### 5. Run the Bot

```bash
python telegram_bot.py
```

Expected startup output:
```text
2026-10-19 20:55:00,000 - [INFO] - qr_telegram_bot - Initializing Telegram Bot application...
2026-10-19 20:55:00,500 - [INFO] - qr_telegram_bot - Starting Telegram Bot long-polling (Press Ctrl+C to stop)...
```

---

## 🧪 Automated Testing

The bot includes an independent test suite verifying input validation, QR image generation, format validity, Unicode preservation, file cleanup, configuration handling, and Telegram mock interactions.

To run the test suite from the `telegram_bot` directory:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Or run the test file directly:

```bash
python tests/test_qr_generation.py -v
```

### What the Tests Cover:
- ✅ Validation of valid URLs, plain text, and Unicode strings
- ✅ Rejection of empty strings, whitespace-only input, and inputs exceeding 2,000 characters
- ✅ Content classification (URLs, Emails, Phone Numbers, Text)
- ✅ PNG image format and dimension verification
- ✅ End-to-end QR decoding matching the original input verbatim
- ✅ Strict deletion and cleanup of temporary PNG image files
- ✅ Error handling when `TELEGRAM_BOT_TOKEN` is unset
- ✅ Verification that desktop GUI/web server is not spawned
- ✅ Asynchronous mocks for Telegram commands, callbacks, and error handler

---

## ☁️ 24/7 Cloud Deployment (Railway)

The bot is ready for deployment on [Railway](https://railway.app) as an autonomous Background Worker.

### Summary of Deployment Settings:
- **Service Type**: Background Worker (no open HTTP ports)
- **Root Directory**: `telegram_bot` (or `QR Code Generator/telegram_bot` if repository root is parent)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python telegram_bot.py`
- **Environment Variable**: `TELEGRAM_BOT_TOKEN`

For detailed step-by-step instructions with screenshots and log verification, read [DEPLOYMENT.md](file:///d:/Work/Coding/Tech%20and%20Digital%20Skills/AI%20&%20ML/Python/carzy%20project%20idea/QR%20Code%20Generator/telegram_bot/DEPLOYMENT.md).

---

## 📂 Project Architecture

```text
QR Code Generator/
│
├── app.py                     # Existing desktop Flask web application (Untouched)
├── static/                    # Desktop web assets (Untouched)
├── templates/                 # Desktop HTML templates (Untouched)
├── requirements.txt           # Desktop application dependencies (Untouched)
├── test_app.py                # Desktop application tests (Untouched)
├── README.md                  # Desktop application documentation (Untouched)
│
└── telegram_bot/              # New independent Telegram Bot package
    ├── telegram_bot.py        # Core bot application & QR generation engine
    ├── requirements.txt       # Minimal bot dependencies (python-telegram-bot, qrcode, pillow)
    ├── .gitignore             # Ignores temp files, virtualenv, and secrets
    ├── DEPLOYMENT.md          # 24/7 Railway Background Worker deployment guide
    ├── README.md              # Bot documentation and setup instructions
    └── tests/
        ├── __init__.py        # Test package marker
        └── test_qr_generation.py  # 31 automated unit and integration tests
```

---

## 🛠️ Troubleshooting & FAQ

### 1. `[ERROR] TELEGRAM_BOT_TOKEN environment variable is not set.`
- **Cause**: The application was launched without providing the environment variable.
- **Solution**: Set the token in your current terminal session (`$env:TELEGRAM_BOT_TOKEN="xyz"` in PowerShell or `export TELEGRAM_BOT_TOKEN="xyz"` in Linux/macOS) before running `python telegram_bot.py`.

### 2. The bot does not respond to messages on Telegram
- **Cause**: The bot process is not running or network connection to `api.telegram.org` is blocked.
- **Solution**: Check your terminal or cloud deployment logs to ensure the bot is polling. Make sure your internet connection or firewall allows outbound HTTPS traffic to Telegram.

### 3. `ModuleNotFoundError: No module named 'telegram'`
- **Cause**: Dependencies are not installed in the active Python environment.
- **Solution**: Activate your virtual environment and run `pip install -r requirements.txt`.

### 4. Can I run both the desktop app and the Telegram bot at the same time?
- **Yes!** The Telegram bot is completely decoupled from the desktop Flask app. Both can run concurrently on the same machine without port conflicts.
