"""
Comprehensive tests for QR Code Generator Telegram Bot.

Tests QR generation logic independently from Telegram, verifies data integrity,
PNG format compliance, Unicode preservation, input validation, cleanup routines,
token configuration, and handles Telegram interactions using mocks.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
from PIL import Image

# Ensure parent directory (telegram_bot) is in path for imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from telegram_bot import (
    CALLBACK_ABOUT,
    CALLBACK_GENERATE,
    CALLBACK_HELP,
    MAX_CONTENT_LENGTH,
    START_MESSAGE,
    HELP_MESSAGE,
    ABOUT_MESSAGE,
    about_command,
    button_callback_handler,
    detect_content_type,
    error_handler,
    generate_qr_code,
    get_bot_token,
    help_command,
    non_text_message_handler,
    start_command,
    text_message_handler,
    validate_content,
)


class TestValidationLogic(unittest.TestCase):
    """Test validation and sanitization of user input."""

    def test_valid_text(self):
        is_valid, msg = validate_content("Hello World")
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    def test_valid_url(self):
        url = "https://example.com/path?arg=1&val=test#hash"
        is_valid, msg = validate_content(url)
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    def test_valid_unicode(self):
        unicode_text = "QR Code 🚀 世界 こんにちは 123 !@#"
        is_valid, msg = validate_content(unicode_text)
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    def test_empty_string(self):
        is_valid, msg = validate_content("")
        self.assertFalse(is_valid)
        self.assertIn("cannot be empty", msg)

    def test_whitespace_only(self):
        is_valid, msg = validate_content("   \t \n  ")
        self.assertFalse(is_valid)
        self.assertIn("cannot be empty", msg)

    def test_none_input(self):
        is_valid, msg = validate_content(None)
        self.assertFalse(is_valid)
        self.assertIn("cannot be empty", msg)

    def test_oversized_input_rejected(self):
        oversized = "A" * (MAX_CONTENT_LENGTH + 1)
        is_valid, msg = validate_content(oversized)
        self.assertFalse(is_valid)
        self.assertIn("too long", msg)

    def test_boundary_length_allowed(self):
        boundary = "A" * MAX_CONTENT_LENGTH
        is_valid, msg = validate_content(boundary)
        self.assertTrue(is_valid)


class TestContentTypeDetection(unittest.TestCase):
    """Test classification of input content types."""

    def test_url_detection(self):
        self.assertEqual(detect_content_type("https://example.com"), "Website URL")
        self.assertEqual(detect_content_type("http://sub.domain.org/test?q=1"), "Website URL")

    def test_email_detection(self):
        self.assertEqual(detect_content_type("mailto:test@example.com"), "Email Address")
        self.assertEqual(detect_content_type("contact@domain.co.uk"), "Email Address")

    def test_phone_detection(self):
        self.assertEqual(detect_content_type("tel:+1234567890"), "Phone Number")
        self.assertEqual(detect_content_type("+1-800-555-0199"), "Phone Number")

    def test_text_detection(self):
        self.assertEqual(detect_content_type("Just a simple text note."), "Text Information")
        self.assertEqual(detect_content_type("Meeting notes: Discuss deployment."), "Text Information")


class TestQRGeneration(unittest.TestCase):
    """Test local QR image generation, format validity, and content decoding."""

    def setUp(self):
        self.detector = cv2.QRCodeDetector()
        self.created_files = []

    def tearDown(self):
        for path in self.created_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def decode_qr_image(self, file_path: str) -> str:
        """Decode a generated PNG image using OpenCV QRCodeDetector."""
        pil_img = Image.open(file_path).convert("RGB")
        cv2_img = np.array(pil_img)[:, :, ::-1].copy()
        decoded_text, _, _ = self.detector.detectAndDecode(cv2_img)
        return decoded_text

    def test_generate_valid_png(self):
        output_file = generate_qr_code("https://example.com")
        self.created_files.append(output_file)

        self.assertTrue(os.path.exists(output_file))
        # Verify it is a valid PNG
        with Image.open(output_file) as img:
            self.assertEqual(img.format, "PNG")
            self.assertGreater(img.width, 100)
            self.assertGreater(img.height, 100)

    def test_exact_content_preservation_url(self):
        test_url = "https://example.com/product?id=999&category=books#reviews"
        output_file = generate_qr_code(test_url)
        self.created_files.append(output_file)

        decoded = self.decode_qr_image(output_file)
        self.assertEqual(decoded, test_url)

    def test_exact_content_preservation_plain_text(self):
        test_text = "Important credentials: User=admin, Pass=secure123!"
        output_file = generate_qr_code(test_text)
        self.created_files.append(output_file)

        decoded = self.decode_qr_image(output_file)
        self.assertEqual(decoded, test_text)

    def test_unicode_qr_generation(self):
        unicode_str = "QR Unicode: 日本語 🌟 العربية Привет"
        output_file = generate_qr_code(unicode_str)
        self.created_files.append(output_file)

        self.assertTrue(os.path.exists(output_file))
        with Image.open(output_file) as img:
            self.assertEqual(img.format, "PNG")

    def test_explicit_output_path(self):
        fd, custom_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        self.created_files.append(custom_path)

        result_path = generate_qr_code("Explicit Output Path Test", output_path=custom_path)
        self.assertEqual(result_path, custom_path)
        self.assertTrue(os.path.exists(custom_path))
        self.assertGreater(os.path.getsize(custom_path), 0)


class TestEnvironmentAndConfiguration(unittest.TestCase):
    """Test configuration, token security, and desktop isolation."""

    def test_missing_token_raises_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                get_bot_token()
            self.assertIn("TELEGRAM_BOT_TOKEN environment variable is not set", str(ctx.exception))

    def test_empty_token_raises_clear_error(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "   "}):
            with self.assertRaises(ValueError) as ctx:
                get_bot_token()
            self.assertIn("TELEGRAM_BOT_TOKEN environment variable is not set", str(ctx.exception))

    def test_valid_token_retrieved(self):
        test_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": test_token}):
            token = get_bot_token()
            self.assertEqual(token, test_token)

    def test_does_not_launch_desktop_gui(self):
        """Verify that telegram_bot module does not import or execute Flask desktop app."""
        # Ensure Flask app instance is not running or imported as a server
        self.assertNotIn("flask.app", sys.modules)


class TestTelegramHandlers(unittest.IsolatedAsyncioTestCase):
    """Test Telegram command, callback, and message handlers using asynchronous mocks."""

    async def test_start_command(self):
        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_context = MagicMock()

        await start_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        args, kwargs = mock_update.message.reply_text.call_args
        self.assertIn("Welcome to QR Code Generator Bot!", args[0])
        reply_markup = kwargs.get("reply_markup")
        self.assertIsNotNone(reply_markup)
        # Check inline buttons
        buttons = [b.text for row in reply_markup.inline_keyboard for b in row]
        self.assertIn("Generate QR Code", buttons)
        self.assertIn("Help", buttons)
        self.assertIn("About", buttons)

    async def test_help_command(self):
        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_context = MagicMock()

        await help_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        args, _ = mock_update.message.reply_text.call_args
        self.assertIn("Help Guide", args[0])

    async def test_about_command(self):
        mock_update = MagicMock()
        mock_update.message = AsyncMock()
        mock_context = MagicMock()

        await about_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        args, _ = mock_update.message.reply_text.call_args
        self.assertIn("About QR Code Generator Bot", args[0])

    async def test_callback_generate_button(self):
        mock_update = MagicMock()
        mock_query = AsyncMock()
        mock_query.data = CALLBACK_GENERATE
        mock_query.message = AsyncMock()
        mock_update.callback_query = mock_query
        mock_context = MagicMock()

        await button_callback_handler(mock_update, mock_context)

        mock_query.answer.assert_awaited_once()
        mock_query.message.reply_text.assert_awaited_once()
        args, _ = mock_query.message.reply_text.call_args
        self.assertIn("Send me any text or URL", args[0])

    async def test_callback_help_button(self):
        mock_update = MagicMock()
        mock_query = AsyncMock()
        mock_query.data = CALLBACK_HELP
        mock_query.message = AsyncMock()
        mock_update.callback_query = mock_query
        mock_context = MagicMock()

        await button_callback_handler(mock_update, mock_context)

        mock_query.answer.assert_awaited_once()
        mock_query.message.reply_text.assert_awaited_once()
        args, _ = mock_query.message.reply_text.call_args
        self.assertIn("Help Guide", args[0])

    async def test_callback_about_button(self):
        mock_update = MagicMock()
        mock_query = AsyncMock()
        mock_query.data = CALLBACK_ABOUT
        mock_query.message = AsyncMock()
        mock_update.callback_query = mock_query
        mock_context = MagicMock()

        await button_callback_handler(mock_update, mock_context)

        mock_query.answer.assert_awaited_once()
        mock_query.message.reply_text.assert_awaited_once()
        args, _ = mock_query.message.reply_text.call_args
        self.assertIn("About QR Code Generator Bot", args[0])

    async def test_text_message_handler_success_and_cleanup(self):
        mock_update = MagicMock()
        mock_message = AsyncMock()
        mock_message.text = "https://example.com"
        mock_update.message = mock_message
        mock_context = MagicMock()

        temp_files_seen = []

        original_open = open

        # Track any temporary file opened during test
        def track_open(path, *args, **kwargs):
            if isinstance(path, str) and "qr_" in path:
                temp_files_seen.append(path)
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=track_open):
            await text_message_handler(mock_update, mock_context)

        # Verify photo was replied
        mock_message.reply_photo.assert_awaited_once()
        _, kwargs = mock_message.reply_photo.call_args
        self.assertIn("QR Code Generated Successfully", kwargs.get("caption", ""))

        # Verify temporary file cleanup
        self.assertGreater(len(temp_files_seen), 0)
        for temp_path in temp_files_seen:
            self.assertFalse(
                os.path.exists(temp_path),
                f"Temporary file was not cleaned up: {temp_path}",
            )

    async def test_text_message_handler_validation_failure(self):
        mock_update = MagicMock()
        mock_message = AsyncMock()
        mock_message.text = "   "
        mock_update.message = mock_message
        mock_context = MagicMock()

        await text_message_handler(mock_update, mock_context)

        mock_message.reply_text.assert_awaited_once()
        args, _ = mock_message.reply_text.call_args
        self.assertIn("Validation Error", args[0])
        mock_message.reply_photo.assert_not_awaited()

    async def test_non_text_message_handler(self):
        mock_update = MagicMock()
        mock_message = AsyncMock()
        mock_update.message = mock_message
        mock_context = MagicMock()

        await non_text_message_handler(mock_update, mock_context)

        mock_message.reply_text.assert_awaited_once()
        args, _ = mock_message.reply_text.call_args
        self.assertIn("Please send text", args[0])

    async def test_error_handler_logs_and_notifies_user(self):
        mock_update = MagicMock()
        mock_message = AsyncMock()
        mock_update.effective_message = mock_message
        mock_context = MagicMock()
        mock_context.error = RuntimeError("Simulated network glitch")

        await error_handler(mock_update, mock_context)

        mock_message.reply_text.assert_awaited_once()
        args, _ = mock_message.reply_text.call_args
        self.assertIn("unexpected error occurred", args[0])


if __name__ == "__main__":
    unittest.main()
