"""Ingest Lambda for Multimodal Agentic Architecture on AWS (S3 events, KB sync, document presign)."""

from __future__ import annotations

from typing import Any

import boto3
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import ValidationError

from agent.schemas import PresignRequest, PresignResponse
from observability.logger import logger, metrics, tracer
from settings import get_settings
from utils.http import json_response, parse_json_body, route_key
from utils.s3 import S3Service


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if "Records" in event:
        return _handle_s3_event(event)

    method_path = route_key(event)
    if event.get("httpMethod") == "OPTIONS" or method_path.startswith("OPTIONS "):
        return json_response(200, {"ok": True})
    try:
        if method_path in {"POST /v1/documents/presign", "POST /documents/presign"}:
            return _handle_presign(event)
        if method_path in {"POST /v1/ingest", "POST /ingest"}:
            job = _start_ingestion_job()
            return json_response(202, {"ingestionJob": job})
        return json_response(404, {"error": "Not found", "route": method_path})
    except ValidationError as exc:
        return json_response(400, {"error": "Invalid request", "details": exc.errors()})
    except Exception:
        logger.exception("unhandled_ingest_handler_error")
        metrics.add_metric(name="UnhandledErrors", unit=MetricUnit.Count, value=1)
        return json_response(500, {"error": "Internal server error"})


def _handle_s3_event(event: dict[str, Any]) -> dict[str, Any]:
    keys = []
    for record in event.get("Records", []):
        bucket = record.get("s3", {}).get("bucket", {}).get("name")
        key = record.get("s3", {}).get("object", {}).get("key")
        if bucket and key:
            keys.append(f"s3://{bucket}/{key}")
    logger.info("s3_ingest_trigger", extra={"objects": keys, "count": len(keys)})
    metrics.add_metric(name="DocumentsUploaded", unit=MetricUnit.Count, value=len(keys))
    job = _start_ingestion_job()
    return {"started": True, "objects": keys, "ingestionJob": job}


def _handle_presign(event: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    req = PresignRequest.model_validate({**parse_json_body(event), "purpose": "document"})
    s3 = S3Service(settings)
    content_type = s3.guess_content_type(req.filename, req.content_type)
    bucket, key = s3.build_object_key(req.filename, "document")
    url = s3.presign_put(bucket, key, content_type)
    return json_response(
        200,
        PresignResponse(
            bucket=bucket,
            key=key,
            url=url,
            expires_in=settings.presign_expires_seconds,
            headers=s3.presign_headers(content_type),
        ).model_dump(),
    )


def _start_ingestion_job() -> dict[str, Any]:
    settings = get_settings()
    if not settings.knowledge_base_id or not settings.data_source_id:
        logger.warning("ingestion_skipped_missing_ids")
        return {"skipped": True, "reason": "KNOWLEDGE_BASE_ID or DATA_SOURCE_ID not set"}
    client = boto3.client("bedrock-agent", region_name=settings.aws_region)
    try:
        response = client.start_ingestion_job(
            knowledgeBaseId=settings.knowledge_base_id,
            dataSourceId=settings.data_source_id,
            description="Triggered by S3 object create or API /v1/ingest",
        )
        job = response.get("ingestionJob") or {}
        metrics.add_metric(name="IngestionJobsStarted", unit=MetricUnit.Count, value=1)
        logger.info("ingestion_job_started", extra={"job_id": job.get("ingestionJobId")})
        return {
            "ingestionJobId": job.get("ingestionJobId"),
            "status": job.get("status"),
        }
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"ConflictException", "ValidationException"}:
            logger.warning("ingestion_job_conflict", extra={"code": code})
            return {"skipped": True, "reason": code}
        raise
