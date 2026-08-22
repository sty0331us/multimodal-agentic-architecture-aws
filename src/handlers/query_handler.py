"""Query Lambda for Multimodal Agentic Architecture on AWS (query, presign, health)."""

from __future__ import annotations

from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from agent.orchestrator import AgentOrchestrator
from agent.schemas import HealthResponse, PresignRequest, PresignResponse, QueryRequest
from observability.logger import logger, metrics, tracer
from settings import get_settings
from utils.http import json_response, parse_json_body, route_key
from utils.s3 import S3Service

_orchestrator: AgentOrchestrator | None = None


def _get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(get_settings())
    return _orchestrator


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    method_path = route_key(event)
    logger.info("query_handler", extra={"route": method_path})

    if event.get("httpMethod") == "OPTIONS" or method_path.startswith("OPTIONS "):
        return json_response(200, {"ok": True})

    if method_path in {"GET /health", "GET /v1/health"}:
        return json_response(
            200, HealthResponse(service=settings.powertools_service_name).model_dump()
        )

    try:
        if method_path in {"POST /v1/query", "POST /query"}:
            return _handle_query(event)
        if method_path in {"POST /v1/uploads/presign", "POST /uploads/presign"}:
            return _handle_presign(event, purpose="upload")
        return json_response(404, {"error": "Not found", "route": method_path})
    except ValidationError as exc:
        return json_response(400, {"error": "Invalid request", "details": exc.errors()})
    except ValueError as exc:
        return json_response(400, {"error": str(exc)})
    except Exception:
        logger.exception("unhandled_query_handler_error")
        metrics.add_metric(name="UnhandledErrors", unit=MetricUnit.Count, value=1)
        return json_response(500, {"error": "Internal server error"})


def _handle_query(event: dict[str, Any]) -> dict[str, Any]:
    body = parse_json_body(event)
    request = QueryRequest.model_validate(body)
    result = _get_orchestrator().run(request)
    metrics.add_metric(name="Queries", unit=MetricUnit.Count, value=1)
    return json_response(200, result.model_dump())


def _handle_presign(event: dict[str, Any], purpose: str) -> dict[str, Any]:
    settings = get_settings()
    req = PresignRequest.model_validate({**parse_json_body(event), "purpose": purpose})
    s3 = S3Service(settings)
    content_type = s3.guess_content_type(req.filename, req.content_type)
    bucket, key = s3.build_object_key(req.filename, req.purpose)
    url = s3.presign_put(bucket, key, content_type)
    metrics.add_metric(name="PresignedUploads", unit=MetricUnit.Count, value=1)
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
