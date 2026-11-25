"""Bounded product-photo validation. Client file names and content types are never trusted."""

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Multipart framing plus the JSON chat state (bounded separately by ChatRequest).
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 512 * 1024
MAX_PIXELS = 40_000_000
MIN_SIDE = 32
MODEL_SIDE = 1024  # Downscale before sending: bounds image tokens and cost.
ALLOWED_TYPES = ("image/png", "image/jpeg", "image/webp")


class UploadRejected(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def sniff_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def normalize_image(data: bytes) -> str:
    """Return a JPEG data URL with EXIF/location metadata removed, or raise UploadRejected."""
    if not data:
        raise UploadRejected(422, "The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected(413, f"Photos must be {MAX_UPLOAD_BYTES // 1024 // 1024} MB or smaller.")
    declared = sniff_type(data)
    if declared is None:
        raise UploadRejected(415, "Unsupported file type. Upload a PNG, JPEG, or WebP photo.")
    unreadable = UploadRejected(422, "The photo could not be read. It may be damaged; try another photo.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            # Check header dimensions before decoding pixels (decompression-bomb guard).
            width, height = image.size
            if width * height > MAX_PIXELS or min(width, height) < MIN_SIDE:
                raise UploadRejected(422, f"Photo dimensions must be at least {MIN_SIDE} px and at most {MAX_PIXELS // 1_000_000} megapixels.")
            if Image.MIME.get(image.format) != declared:
                raise unreadable
            image.load()
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGBA", image.size, (255, 255, 255, 255))
                image = Image.alpha_composite(background, image)
            image = image.convert("RGB")
            image.thumbnail((MODEL_SIDE, MODEL_SIDE))
            output = io.BytesIO()
            # Re-encoding writes pixels only; EXIF, GPS, and embedded text chunks are dropped.
            image.save(output, "JPEG", quality=88)
    except UploadRejected:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise unreadable from error
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
