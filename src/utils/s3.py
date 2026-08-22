"""S3 helpers for uploads, documents, and presigned URLs."""

from __future__ import annotations

import mimetypes
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.config import Config

from settings import Settings


class S3Service:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client or boto3.client(
            "s3",
            region_name=settings.aws_region,
            config=Config(signature_version="s3v4"),
        )

    def get_bytes(self, bucket: str, key: str) -> bytes:
        obj = self._client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    def _sse_params(self) -> dict[str, str]:
        params = {"ServerSideEncryption": "aws:kms"}
        if self._settings.kms_key_id:
            params["SSEKMSKeyId"] = self._settings.kms_key_id
        return params

    def put_bytes(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            **self._sse_params(),
        )

    def presign_put(self, bucket: str, key: str, content_type: str) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ContentType": content_type,
                **self._sse_params(),
            },
            ExpiresIn=self._settings.presign_expires_seconds,
        )

    def presign_headers(self, content_type: str) -> dict[str, str]:
        headers = {
            "Content-Type": content_type,
            "x-amz-server-side-encryption": "aws:kms",
        }
        if self._settings.kms_key_id:
            headers["x-amz-server-side-encryption-aws-kms-key-id"] = self._settings.kms_key_id
        return headers

    def build_object_key(self, filename: str, purpose: str) -> tuple[str, str]:
        safe = filename.replace("..", "").lstrip("/")
        ext = ""
        if "." in safe:
            ext = "." + safe.rsplit(".", 1)[-1].lower()
        stamp = datetime.now(UTC).strftime("%Y/%m/%d")
        key_id = uuid.uuid4().hex
        if purpose == "document":
            bucket = self._settings.documents_bucket
            key = f"{self._settings.documents_prefix}{stamp}/{key_id}{ext}"
        else:
            bucket = self._settings.uploads_bucket
            key = f"uploads/{stamp}/{key_id}{ext}"
        return bucket, key

    @staticmethod
    def guess_content_type(filename: str, fallback: str) -> str:
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or fallback
