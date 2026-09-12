"""Downloads a post's thumbnail image and re-encodes it small, so we can
store it permanently in Postgres. Instagram's CDN URLs are signed and expire
(often within days), so hotlinking `media_url` long-term isn't reliable -
we grab the bytes once, right after scraping, while the link is still fresh.
"""
from __future__ import annotations

import io
import urllib.request

from PIL import Image

MAX_WIDTH = 400
JPEG_QUALITY = 75


def fetch_thumbnail(media_url: str) -> bytes | None:
    if not media_url:
        return None
    try:
        req = urllib.request.Request(media_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        return to_jpeg(raw)
    except Exception:  # noqa: BLE001 - a missing thumbnail shouldn't fail the whole post
        return None


def to_jpeg(image_bytes: bytes) -> bytes | None:
    """Re-encodes arbitrary image bytes (PNG, WEBP, etc.) to a small JPEG -
    every vision-classification call in this codebase assumes JPEG bytes
    (hardcodes that media_type), so any image captured a different way (e.g.
    a raw PNG from a Playwright screenshot) must be normalized through this
    before it's stored or sent to Claude, or classification silently
    mismatches its own declared media_type."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / img.width
            img = img.resize((MAX_WIDTH, int(img.height * ratio)))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY)
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return None
