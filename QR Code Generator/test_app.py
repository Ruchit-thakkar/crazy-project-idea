import base64
import io
import unittest
import cv2
import numpy as np
from PIL import Image

from app import app, validate_url


class QRCodeGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.detector = cv2.QRCodeDetector()

    def decode_base64_qr(self, data_uri: str) -> str:
        """Decode base64 PNG data URI using OpenCV QRCodeDetector."""
        header, base64_data = data_uri.split(",", 1)
        image_bytes = base64.b64decode(base64_data)
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        cv2_img = np.array(pil_img)
        # Convert RGB to BGR for OpenCV
        cv2_img = cv2_img[:, :, ::-1].copy()
        
        decoded_text, points, _ = self.detector.detectAndDecode(cv2_img)
        return decoded_text

    def test_url_validation_valid(self):
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://google.com",
            "https://instagram.com/example",
            "https://sub.domain.co.uk/path/to/page?query=true&id=99#section",
            "https://example.com/product?id=123&utm_source=qr#details",
            "http://localhost:8080/test",
            "http://127.0.0.1:5000/app",
        ]
        for url in valid_urls:
            is_valid, msg = validate_url(url)
            self.assertTrue(is_valid, f"Expected '{url}' to be valid, but got: {msg}")

    def test_url_validation_invalid(self):
        invalid_urls = [
            "",
            "   ",
            "example.com",  # Missing http:// or https://
            "ftp://files.example.com",
            "javascript:alert(1)",
            "https://",
            "http://",
            "https://invalid domain with spaces.com",
            "just plain text",
        ]
        for url in invalid_urls:
            is_valid, msg = validate_url(url)
            self.assertFalse(is_valid, f"Expected '{url}' to be invalid, but passed validation")

    def test_generate_endpoint_exact_encoding(self):
        test_cases = [
            "https://example.com",
            "https://google.com",
            "https://instagram.com/example",
            "https://example.com/product?id=123&utm_source=qr#details",
        ]
        for original_url in test_cases:
            resp = self.client.post("/generate", json={"url": original_url})
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["url"], original_url)
            self.assertTrue(data["qr_image"].startswith("data:image/png;base64,"))

            # Decode the generated QR code and verify exact match
            decoded_url = self.decode_base64_qr(data["qr_image"])
            self.assertEqual(
                decoded_url,
                original_url,
                f"QR Code decoded to '{decoded_url}', which does not match '{original_url}'"
            )

    def test_generate_endpoint_invalid_url(self):
        resp = self.client.post("/generate", json={"url": "not-a-valid-url"})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_download_endpoint(self):
        target_url = "https://example.com"
        resp = self.client.get(f"/download?url={target_url}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/png")
        self.assertIn("attachment", resp.headers.get("Content-Disposition", ""))


if __name__ == "__main__":
    unittest.main()
