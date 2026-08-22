"""Image decode helpers."""

from __future__ import annotations

import base64

from utils.images import decode_base64_image, detect_format


def test_detect_png_magic() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    assert detect_format(png) == "png"


def test_decode_data_url() -> None:
    raw = b"hello-bytes"
    payload = "data:image/png;base64," + base64.b64encode(raw).decode()
    assert decode_base64_image(payload) == raw
