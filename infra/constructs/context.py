"""Typed CDK context helpers."""

from __future__ import annotations

from typing import Any

from constructs import Construct


def ctx(scope: Construct, key: str, default: Any) -> Any:
    value = scope.node.try_get_context(key)
    return default if value is None or value == "" else value


def ctx_bool(scope: Construct, key: str, default: bool = True) -> bool:
    value = ctx(scope, key, default)
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}
