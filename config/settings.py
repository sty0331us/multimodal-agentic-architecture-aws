"""Compatibility wrapper so local scripts can `from config.settings import get_settings`."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from settings import Settings, get_settings  # noqa: E402

__all__ = ["Settings", "get_settings"]
