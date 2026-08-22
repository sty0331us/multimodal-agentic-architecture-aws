"""Powertools logger/tracer/metrics factory."""

from __future__ import annotations

from aws_lambda_powertools import Logger, Metrics, Tracer

from settings import get_settings

_settings = get_settings()

logger = Logger(service=_settings.powertools_service_name, level=_settings.log_level)
tracer = Tracer(service=_settings.powertools_service_name)
metrics = Metrics(
    namespace=_settings.powertools_metrics_namespace,
    service=_settings.powertools_service_name,
)


def get_logger(_name: str | None = None) -> Logger:
    return logger
