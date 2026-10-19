"""
Telegram Bot for QR Code Generation.

Runs independently 24/7 as a background worker on cloud infrastructure (e.g., Railway).
Accepts text, URLs, email addresses, phone numbers, and Unicode input, generating
high-quality, scannable QR codes sent directly to users on Telegram.
"""

import logging
import os
import re
import sys
import tempfile
from typing import Final
from urllib.parse import urlsplit

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
)
# Silence verbose httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("qr_telegram_bot")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_CONTENT_LENGTH: Final[int] = 2000

START_MESSAGE: Final[str] = (
    "Welcome to QR Code Generator Bot!\n\n"
    "Generate QR codes instantly from text, URLs, email addresses, "
    "phone numbers, and other text-based information.\n\n"
    "Send me any text or URL to generate your QR code."
)

HELP_MESSAGE: Final[str] = (
    "📖 *QR Code Generator Bot - Help Guide*\n\n"
    "Generate instant, scannable QR codes with zero data retention.\n\n"
    "📌 *How to use:*\n"
    "Simply send me any text or link directly in this chat:\n"
    "• *Website URL:* `https://example.com`\n"
    "• *Plain Text:* Any note, address, or message\n"
    "• *Email:* `mailto:hello@example.com` or `hello@example.com`\n"
    "• *Phone:* `tel:+1234567890` or `+1234567890`\n"
    "• *Wi-Fi credentials or location coordinates*\n\n"
    "🌐 *Unicode & International:* Full support for emojis and all language scripts.\n\n"
    "⌨️ *Available Commands:*\n"
    "/start - Start the bot & show navigation menu\n"
    "/help - Display this help guide\n"
    "/about - Bot specifications & privacy info"
)

ABOUT_MESSAGE: Final[str] = (
    "ℹ️ *About QR Code Generator Bot*\n\n"
    "🚀 *Fast & Reliable:* Local image generation using Python and Pillow.\n"
    "🔒 *Private by Design:* No user content or generated images are permanently stored. "
    "Temporary files are strictly removed immediately after sending.\n"
    "📷 *Universal Compatibility:* Adheres to ISO/IEC 18004 QR standards with "
    "Error Correction Level M (15% redundancy) and standard quiet-zone margins.\n"
    "☁️ *Cloud Ready:* Designed for 24/7 autonomous execution on Railway or any container host."
)

CALLBACK_GENERATE: Final[str] = "btn_generate"
CALLBACK_HELP: Final[str] = "btn_help"
CALLBACK_ABOUT: Final[str] = "btn_about"


# ---------------------------------------------------------------------------
# Inline Keyboards
# ---------------------------------------------------------------------------
def get_start_keyboard() -> InlineKeyboardMarkup:
    """Return inline navigation buttons for /start."""
    keyboard = [
        [InlineKeyboardButton("Generate QR Code", callback_data=CALLBACK_GENERATE)],
        [
            InlineKeyboardButton("Help", callback_data=CALLBACK_HELP),
            InlineKeyboardButton("About", callback_data=CALLBACK_ABOUT),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ---------------------------------------------------------------------------
# QR Generation & Validation Logic (Standalone)
# ---------------------------------------------------------------------------
def validate_content(text: str | None) -> tuple[bool, str]:
    """
    Validate input text for QR code generation.
    Returns (is_valid, error_message).
    """
    if text is None or not isinstance(text, str):
        return False, "Input cannot be empty. Please send text, a URL, email, or phone number."

    cleaned = text.strip()
    if not cleaned:
        return False, "Input cannot be empty. Please send text, a URL, email, or phone number."

    if len(cleaned) > MAX_CONTENT_LENGTH:
        return (
            False,
            f"Input is too long ({len(cleaned):,} characters). "
            f"The maximum allowed length is {MAX_CONTENT_LENGTH:,} characters.",
        )

    return True, ""


def detect_content_type(text: str) -> str:
    """Classify the content type for user-friendly feedback."""
    cleaned = text.strip()
    try:
        parsed = urlsplit(cleaned)
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            return "Website URL"
    except Exception:
        pass

    if cleaned.lower().startswith("mailto:") or re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned):
        return "Email Address"
    if cleaned.lower().startswith("tel:") or re.match(r"^\+?[0-9\s\-()]{7,20}$", cleaned):
        return "Phone Number"
    return "Text Information"


def generate_qr_code(data: str, output_path: str | None = None) -> str:
    """
    Generate a high-resolution QR code preserving complete input data.

    - Error correction: M (15% error recovery for reliable scanning)
    - Box size: 10 (crisp high-resolution PNG)
    - Border: 4 (standard quiet zone required by QR specification)
    - Colors: Crisp black pattern on pure white background

    Returns the absolute path to the generated PNG file.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    if output_path is None:
        fd, temp_file_path = tempfile.mkstemp(prefix="qr_", suffix=".png")
        os.close(fd)
        output_path = temp_file_path

    img.save(output_path, format="PNG")
    return output_path


# ---------------------------------------------------------------------------
# Bot Command & Callback Handlers
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    if not update.message:
        return
    await update.message.reply_text(
        START_MESSAGE,
        reply_markup=get_start_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    if not update.message:
        return
    await update.message.reply_text(
        HELP_MESSAGE,
        parse_mode=ParseMode.MARKDOWN,
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /about command."""
    if not update.message:
        return
    await update.message.reply_text(
        ABOUT_MESSAGE,
        parse_mode=ParseMode.MARKDOWN,
    )


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if query.data == CALLBACK_GENERATE:
        await query.message.reply_text(
            "Send me any text or URL to generate your QR code.",
        )
    elif query.data == CALLBACK_HELP:
        await query.message.reply_text(
            HELP_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
        )
    elif query.data == CALLBACK_ABOUT:
        await query.message.reply_text(
            ABOUT_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
        )


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process incoming user text and send back the generated QR code."""
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text
    is_valid, error_msg = validate_content(raw_text)

    if not is_valid:
        await update.message.reply_text(
            f"❌ *Validation Error:*\n{error_msg}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    cleaned_text = raw_text.strip()
    content_type = detect_content_type(cleaned_text)

    # Indicate upload activity to user
    await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

    temp_image_path: str | None = None
    try:
        temp_image_path = generate_qr_code(cleaned_text)

        preview = cleaned_text if len(cleaned_text) <= 60 else f"{cleaned_text[:57]}..."
        # Escape markdown characters in preview for safe formatting
        escaped_preview = re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", preview)

        caption = (
            "✅ *QR Code Generated Successfully!*\n\n"
            f"📦 *Type:* {content_type}\n"
            f"📏 *Length:* {len(cleaned_text)} characters\n"
            f"📝 *Preview:* `{escaped_preview}`\n\n"
            "Scan with your mobile camera or any QR scanner."
        )

        with open(temp_image_path, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )

    except Exception as exc:
        logger.error("Failed to generate or send QR code: %s", exc, exc_info=True)
        await update.message.reply_text(
            "⚠️ An error occurred while generating your QR code. "
            "Please check your input and try again."
        )
    finally:
        # Strictly delete temporary file after processing
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
            except OSError as err:
                logger.warning("Could not delete temporary file %s: %s", temp_image_path, err)


async def non_text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-text messages (stickers, documents, media) gracefully."""
    if not update.message:
        return
    await update.message.reply_text(
        "ℹ️ Please send text, a website URL, email, or phone number to generate a QR code.",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unexpected errors across bot execution."""
    # Never log tokens or sensitive data
    logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)

    effective_message = getattr(update, "effective_message", None)
    if effective_message:
        try:
            await effective_message.reply_text(
                "⚠️ An unexpected error occurred while processing your request. Please try again later."
            )
        except TelegramError:
            # If sending error fails, avoid crash
            pass


# ---------------------------------------------------------------------------
# Application Factory & Configuration
# ---------------------------------------------------------------------------
def get_bot_token() -> str:
    """
    Retrieve Telegram Bot Token from the environment variable.
    Raises ValueError if unset or empty.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Please configure your bot token before starting the application."
        )
    return token


def build_application(token: str) -> Application:
    """Construct and configure the Telegram Bot Application."""
    app = ApplicationBuilder().token(token).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))

    # Inline callback query handler
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, non_text_message_handler))

    # Error handler
    app.add_error_handler(error_handler)

    return app


def main() -> None:
    """Main entrypoint for running the Telegram Bot."""
    try:
        token = get_bot_token()
    except ValueError as err:
        sys.stderr.write(f"\n[ERROR] {err}\n\n")
        sys.stderr.write("Usage:\n")
        sys.stderr.write("  export TELEGRAM_BOT_TOKEN=\"your_bot_token_here\"\n")
        sys.stderr.write("  python telegram_bot.py\n\n")
        sys.exit(1)

    logger.info("Initializing Telegram Bot application...")
    application = build_application(token)

    logger.info("Starting Telegram Bot long-polling (Press Ctrl+C to stop)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
