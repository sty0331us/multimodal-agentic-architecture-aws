"""HTTP helpers for API Gateway proxy responses."""

from __future__ import annotations

import json
from typing import Any

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def json_response(status_code: int, body: dict[str, Any] | list[Any] | str) -> dict[str, Any]:
    payload = body if isinstance(body, str) else json.dumps(body, default=str)
    return {"statusCode": status_code, "headers": CORS_HEADERS, "body": payload}


def parse_json_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    if isinstance(body, dict):
        return body
    return json.loads(body or "{}")


def route_key(event: dict[str, Any]) -> str:
    method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method")
        or "GET"
    )
    path = event.get("path") or event.get("rawPath") or "/"
    stage = (event.get("requestContext") or {}).get("stage")
    if stage and path.startswith(f"/{stage}/"):
        path = path[len(stage) + 1 :]
    return f"{method.upper()} {path.rstrip('/') or '/'}"
