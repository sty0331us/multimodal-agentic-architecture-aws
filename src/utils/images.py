"""Image fetch, decode, and format detection."""

from __future__ import annotations

import base64
import binascii
import urllib.request
from dataclasses import dataclass
from typing import Literal

from agent.schemas import QueryRequest

ImageFormat = Literal["png", "jpeg", "gif", "webp"]

_MAGIC: list[tuple[bytes, ImageFormat]] = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"RIFF", "webp"),
]


@dataclass
class ResolvedImage:
    data: bytes
    fmt: ImageFormat
    bucket: str | None = None
    key: str | None = None


def detect_format(data: bytes, declared: ImageFormat | None = None) -> ImageFormat:
    if declared:
        return declared
    for magic, fmt in _MAGIC:
        if data.startswith(magic):
            if fmt == "webp" and b"WEBP" not in data[:16]:
                continue
            return fmt
    return "jpeg"


def decode_base64_image(payload: str) -> bytes:
    raw = payload.split(",", 1)[-1].strip()
    try:
        return base64.b64decode(raw, validate=False)
    except binascii.Error as exc:
        raise ValueError("Invalid image_base64 payload") from exc


def fetch_url(url: str, timeout: int = 10, max_bytes: int = 5_000_000) -> bytes:
    if not url.startswith(("https://", "http://")):
        raise ValueError("image_url must be http(s)")
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Remote image exceeds size limit")
    return data


def resolve_image(request: QueryRequest, s3_get_bytes) -> ResolvedImage | None:
    """Load image bytes from S3, URL, or base64. `s3_get_bytes(bucket, key) -> bytes`."""
    if request.image:
        data = s3_get_bytes(request.image.bucket, request.image.key)
        return ResolvedImage(
            data=data,
            fmt=detect_format(data, request.image_format),
            bucket=request.image.bucket,
            key=request.image.key,
        )
    if request.image_base64:
        data = decode_base64_image(request.image_base64)
        return ResolvedImage(data=data, fmt=detect_format(data, request.image_format))
    if request.image_url:
        data = fetch_url(request.image_url)
        return ResolvedImage(data=data, fmt=detect_format(data, request.image_format))
    return None
