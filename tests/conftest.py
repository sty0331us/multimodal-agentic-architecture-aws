"""Pytest path and environment bootstrap."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "multimodal-agentic-architecture-aws-test")
os.environ.setdefault("POWERTOOLS_TRACE_DISABLED", "true")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "MultimodalAgenticArchitectureAwsTest")
os.environ.setdefault("LOG_LEVEL", "INFO")


def lambda_context() -> SimpleNamespace:
    return SimpleNamespace(
        function_name="query-handler-test",
        memory_limit_in_mb=1024,
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:query-handler-test",
        aws_request_id="00000000-0000-0000-0000-000000000000",
    )
