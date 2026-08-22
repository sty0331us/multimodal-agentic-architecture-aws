"""Placeholder for live AWS tests. Run after `cdk deploy` with real credentials."""

from __future__ import annotations

import os

import pytest


@pytest.mark.integration
def test_env_has_api_url() -> None:
    if not os.getenv("API_BASE_URL"):
        pytest.skip("API_BASE_URL not set")
    assert os.environ["API_BASE_URL"].startswith("https://")
