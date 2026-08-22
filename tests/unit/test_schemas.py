"""Unit tests for request contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.schemas import QueryRequest


def test_text_only_query() -> None:
    req = QueryRequest(query="What is our PPE policy?")
    assert req.has_image is False


def test_rejects_multiple_image_sources() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(
            query="look",
            image_url="https://example.com/a.png",
            image_base64="aaaa",
        )


def test_s3_image_ref() -> None:
    req = QueryRequest(query="describe", image={"bucket": "b", "key": "k.png"})
    assert req.has_image is True
    assert req.image is not None
    assert req.image.bucket == "b"
