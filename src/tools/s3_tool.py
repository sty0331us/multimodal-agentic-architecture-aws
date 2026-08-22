"""S3 document helper exposed as a tool for ingestion-status style lookups."""

from __future__ import annotations

from typing import Any

from tools.base import Tool
from utils.s3 import S3Service


class S3UploadTool(Tool):
    name = "describe_s3_object"
    description = (
        "Read object metadata for an uploaded image or document in the controlled buckets. "
        "Use only for objects in the uploads or documents buckets."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "key": {"type": "string"},
        },
        "required": ["bucket", "key"],
    }

    def __init__(
        self, s3: S3Service, allowed_buckets: list[str], client: Any | None = None
    ) -> None:
        self._s3 = s3
        self._allowed = set(allowed_buckets)
        self._client = client or s3._client  # noqa: SLF001

    def invoke(self, tool_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        bucket = tool_input["bucket"]
        key = tool_input["key"]
        if bucket not in self._allowed:
            raise ValueError("Bucket is not in the allow-list")
        head = self._client.head_object(Bucket=bucket, Key=key)
        return {
            "bucket": bucket,
            "key": key,
            "content_type": head.get("ContentType"),
            "content_length": head.get("ContentLength"),
            "sse": head.get("ServerSideEncryption"),
        }
