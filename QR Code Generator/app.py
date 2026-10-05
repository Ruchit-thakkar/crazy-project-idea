import base64
import io
import re
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request, send_file
import qrcode
from qrcode.constants import ERROR_CORRECT_M

app = Flask(__name__)

# Basic hostname pattern (domain names, localhost, or IPv4)
HOSTNAME_REGEX = re.compile(
    r"^(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}|localhost|\d{1,3}(?:\.\d{1,3}){3})(?::\d{1,5})?$"
)


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validates that the input is a well-formed website URL with http or https scheme.
    Returns (is_valid, error_message).
    """
    if not url or not isinstance(url, str):
        return False, "URL cannot be empty. Please enter a valid website URL."

    cleaned_url = url.strip()

    if len(cleaned_url) > 2000:
        return False, "URL is too long (maximum 2,000 characters allowed)."

    try:
        parsed = urlsplit(cleaned_url)
    except Exception:
        return False, "Invalid URL structure."

    if parsed.scheme.lower() not in ("http", "https"):
        return False, "URL must start with http:// or https:// (e.g., https://example.com)."

    if not parsed.netloc:
        return False, "URL must include a valid domain or host (e.g., example.com)."

    # Remove credentials (user:pass@) if any to validate hostname
    host = parsed.netloc.split("@")[-1]
    if not HOSTNAME_REGEX.match(host):
        return False, f"Invalid domain name or host: '{host}'."

    return True, ""


def generate_qr_image(url: str):
    """
    Generates a high-quality QR code image for the exact URL.
    - Error correction: M (15% recovery, reliable camera scanning)
    - Box size: 10 (crisp high-resolution)
    - Border: 4 (standard quiet zone required by QR spec)
    - Fill: Black pattern on pure White background
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    # Encode exact URL without altering query params, fragments, or cases
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def sanitize_filename(url: str) -> str:
    """Generate a clean filename for PNG download based on host."""
    try:
        parsed = urlsplit(url)
        host = re.sub(r"[^a-zA-Z0-9.-]", "_", parsed.netloc)
        return f"qr_{host}.png" if host else "qr_code.png"
    except Exception:
        return "qr_code.png"


@app.route("/")
def index():
    """Render the main QR Generator page."""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """API endpoint to generate a QR code from a submitted URL."""
    data = request.get_json(silent=True) or request.form

    raw_url = data.get("url", "")
    if not raw_url:
        return jsonify({"success": False, "error": "Please enter a website URL."}), 400

    url = raw_url.strip()
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    try:
        img = generate_qr_image(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{img_base64}"
        filename = sanitize_filename(url)

        return jsonify({
            "success": True,
            "url": url,
            "qr_image": data_uri,
            "filename": filename,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to generate QR code: {str(e)}",
        }), 500


@app.route("/download", methods=["GET"])
def download():
    """Endpoint allowing direct browser download of the QR code as a PNG file."""
    url = request.args.get("url", "").strip()
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    try:
        img = generate_qr_image(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        filename = sanitize_filename(url)
        return send_file(
            buf,
            mimetype="image/png",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    # Run locally on port 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
