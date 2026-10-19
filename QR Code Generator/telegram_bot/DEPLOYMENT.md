# 🚀 24/7 Cloud Deployment Guide: Railway Background Worker

This guide provides step-by-step instructions for deploying the **QR Code Generator Telegram Bot** as an autonomous background worker on [Railway](https://railway.app) to keep it running **24/7 online** without requiring your local machine to stay powered on.

---

## 📋 Overview & Requirements

- **Service Type:** Background Worker (no public HTTP port or web listener required).
- **Runtime:** Python 3.10+
- **Execution Directory:** `telegram_bot`
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  python telegram_bot.py
  ```
- **Required Environment Variable:**
  ```bash
  TELEGRAM_BOT_TOKEN
  ```

---

## 🛠️ Step-by-Step Deployment Instructions

### Step 1: Create a Bot via Telegram's Official BotFather

1. Open Telegram and search for the official account [@BotFather](https://t.me/BotFather) (verified blue checkmark).
2. Send `/start` to see all available commands.
3. Send `/newbot` to start the bot creation wizard.
4. Enter a display name (e.g., `My QR Code Generator Bot`).
5. Choose a unique username ending in `bot` (e.g., `MyCustomQRGenerator_bot`).
6. BotFather will provide an **HTTP API Token** formatted like:
   ```text
   123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   ```
7. **Security Warning:** Keep this token private. Never commit it to GitHub, publish it in public repositories, or send it in unsecured messages.

---

### Step 2: Push Your Project to GitHub

Ensure all your project files, including the new `telegram_bot/` directory, are committed and pushed to your GitHub repository:

```bash
git add .
git commit -m "Add Telegram QR bot with tests and deployment configs"
git push origin main
```

*(Note: The `.gitignore` inside `telegram_bot/` prevents accidental commits of virtual environments or secret tokens).*

---

### Step 3: Create a Railway Account & Connect Repository

1. Sign up or log into [Railway.app](https://railway.app).
2. Click **"+ New Project"** on the Railway dashboard.
3. Select **"Deploy from GitHub repo"**.
4. Authorize Railway and select your repository (`QR Code Generator` or your parent repository).

---

### Step 4: Configure the Service as a Background Worker

Because the bot operates via Telegram long-polling, it does not listen on an HTTP port. Configure it as a background worker:

#### 1. Configure Root Directory
If your Git repository contains the bot inside the `telegram_bot` folder (or `QR Code Generator/telegram_bot` if deploying the monorepo root):
1. In your Railway dashboard, click on the newly created service.
2. Go to **Settings** > **General**.
3. Locate **Root Directory** and click **Edit**.
4. Set the Root Directory to:
   - `telegram_bot` (if the repo root is `QR Code Generator`)
   - `QR Code Generator/telegram_bot` (if the repo root is the entire workspace)
5. Save changes.

#### 2. Configure Build & Start Commands
Under **Settings** > **Build & Deploy**:
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  python telegram_bot.py
  ```

> **Alternative: Monorepo Root Setup**
> If your hosting platform does not support changing the Root Directory, leave Root Directory as `/` and specify the custom commands directly:
> - **Build Command:** `pip install -r "QR Code Generator/telegram_bot/requirements.txt"`
> - **Start Command:** `python "QR Code Generator/telegram_bot/telegram_bot.py"`

---

### Step 5: Configure Environment Variables

1. Go to the **Variables** tab of your service in Railway.
2. Click **"+ New Variable"** (or **"Raw Editor"**).
3. Add the required bot token:
   - **Variable Name:** `TELEGRAM_BOT_TOKEN`
   - **Value:** Paste your token obtained from BotFather (e.g., `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
4. Click **Add**.

---

### Step 6: Deploy the Worker & Inspect Logs

1. Railway automatically triggers a new deployment when environment variables or code changes are saved.
2. Navigate to the **Deployments** tab.
3. Click on the active deployment and open the **Deploy Logs**.
4. Confirm successful startup:
   ```text
   [INFO] - qr_telegram_bot - Initializing Telegram Bot application...
   [INFO] - qr_telegram_bot - Starting Telegram Bot long-polling (Press Ctrl+C to stop)...
   ```
5. If you see any errors (e.g., `TELEGRAM_BOT_TOKEN environment variable is not set`), verify that the variable was added correctly under the **Variables** tab and trigger a redeploy.

---

### Step 7: Verify Online Functionality

1. Open Telegram on your phone or desktop.
2. Search for your bot username and open the chat.
3. Send `/start`.
   - Verify that the welcome message and inline buttons appear.
4. Send a website URL (e.g., `https://google.com`).
   - Verify that the bot sends back a crisp QR code PNG with a success confirmation.
5. Send a plain text note or Unicode string (e.g., `Hello 🚀`).
   - Verify the generated QR code.

---

## 💳 Railway Usage & Plan Notes

- **Pricing & Limits:** Railway provides free trial credits upon initial sign-up, after which usage requires a paid plan (such as the Hobby Plan).
- **Background Worker Resource Consumption:** Because this bot consumes minimal CPU and memory (typically under 60MB RAM during polling and small bursts during image generation), resource usage is very cost-effective.
- **Always-On Persistence:** As long as your Railway project remains active and within your plan's execution limits, the bot will run 24/7 without needing your laptop or local environment.
- **Zero Inbound Port Requirement:** Telegram bots using polling do not need incoming public IP addresses, domain names, or SSL certificates.

---

## 🔍 Deployment Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Crash: `TELEGRAM_BOT_TOKEN environment variable is not set`** | Missing environment variable in Railway | Open the **Variables** tab in Railway, add `TELEGRAM_BOT_TOKEN`, and redeploy. |
| **`ModuleNotFoundError: No module named 'telegram'`** | Dependencies failed to install or wrong directory | Verify Root Directory is set to `telegram_bot` and build command is `pip install -r requirements.txt`. |
| **Worker exits immediately with code 0** | Bot process stopped prematurely | Ensure the start command is `python telegram_bot.py` and that `application.run_polling()` is called. |
| **Network timeout / Connection refused** | Outbound internet restriction on host | Ensure your Railway worker has outbound network access enabled to connect to Telegram's API (`api.telegram.org`). |
