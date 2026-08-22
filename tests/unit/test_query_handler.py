"""Query Lambda routing tests."""

from __future__ import annotations

import json

from agent.schemas import QueryResponse
from handlers import query_handler
from tests.conftest import lambda_context


def test_health(monkeypatch) -> None:
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "test")
    event = {"httpMethod": "GET", "path": "/v1/health"}
    response = query_handler.lambda_handler(event, lambda_context())
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ok"


def test_query_validation_error() -> None:
    event = {"httpMethod": "POST", "path": "/v1/query", "body": "{}"}
    response = query_handler.lambda_handler(event, lambda_context())
    assert response["statusCode"] == 400


def test_query_success(monkeypatch) -> None:
    class FakeOrch:
        def run(self, request):
            return QueryResponse(
                answer="ok",
                stop_reason="end_turn",
                model_id="test-model",
            )

    monkeypatch.setattr(query_handler, "_get_orchestrator", lambda: FakeOrch())
    event = {
        "httpMethod": "POST",
        "path": "/v1/query",
        "body": json.dumps({"query": "hello"}),
    }
    response = query_handler.lambda_handler(event, lambda_context())
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["answer"] == "ok"
