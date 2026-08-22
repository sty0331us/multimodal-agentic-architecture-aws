"""Live API checks. Requires API_BASE_URL and API_KEY."""

from __future__ import annotations

import os

import pytest


@pytest.mark.e2e
def test_health_live() -> None:
    base = os.getenv("API_BASE_URL")
    if not base:
        pytest.skip("API_BASE_URL not set")
    import urllib.request

    with urllib.request.urlopen(base.rstrip("/") + "/v1/health", timeout=15) as resp:  # noqa: S310
        assert resp.status == 200
