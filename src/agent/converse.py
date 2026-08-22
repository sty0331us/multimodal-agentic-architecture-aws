"""Amazon Bedrock Converse API client with per-request model routing and Guardrails."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from models import SONNET_5_ID_SUBSTRING
from observability.logger import get_logger
from settings import Settings

logger = get_logger(__name__)

_RETRY = Config(retries={"max_attempts": 5, "mode": "adaptive"})


def is_claude_sonnet_5(model_id: str) -> bool:
    return SONNET_5_ID_SUBSTRING in model_id


class BedrockConverseClient:
    """Bedrock Converse client. Payload shape depends on the selected model id."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client or boto3.client(
            "bedrock-runtime", region_name=settings.aws_region, config=_RETRY
        )

    def converse(
        self,
        *,
        messages: list[dict[str, Any]],
        system: list[dict[str, str]],
        tool_config: dict[str, Any] | None = None,
        inference_config: dict[str, Any] | None = None,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        kwargs = self.build_request(
            messages=messages,
            system=system,
            tool_config=tool_config,
            inference_config=inference_config,
            model_id=model_id,
        )
        logger.info(
            "bedrock_converse_start",
            extra={
                "model_id": kwargs["modelId"],
                "guardrail": bool(self._settings.guardrail_identifier),
                "tools": bool(tool_config),
                "thinking": kwargs.get("additionalModelRequestFields", {}).get("thinking"),
            },
        )
        try:
            response = self._client.converse(**kwargs)
        except (ClientError, BotoCoreError):
            logger.exception("bedrock_converse_failed")
            raise
        logger.info(
            "bedrock_converse_complete",
            extra={
                "model_id": kwargs["modelId"],
                "stop_reason": response.get("stopReason"),
                "usage": response.get("usage"),
            },
        )
        return response

    def build_request(
        self,
        *,
        messages: list[dict[str, Any]],
        system: list[dict[str, str]],
        tool_config: dict[str, Any] | None = None,
        inference_config: dict[str, Any] | None = None,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a Converse payload for the selected tier.

        Claude Sonnet 5: adaptive thinking on; omit temperature.
        Claude 4.5 Haiku (fast tier): temperature allowed; no thinking block
        (Haiku 4.5 supports extended thinking, but the fast path omits it for
        latency and token cost).
        Guardrails are attached whenever configured, for every tier.
        """
        resolved = model_id or self._settings.resolved_reasoning_model_id
        kwargs: dict[str, Any] = {
            "modelId": resolved,
            "messages": messages,
            "system": system,
            "inferenceConfig": inference_config
            or self._default_inference_config(resolved),
        }
        extra = self._additional_model_request_fields(resolved)
        if extra:
            kwargs["additionalModelRequestFields"] = extra
        if tool_config:
            kwargs["toolConfig"] = tool_config
        if self._settings.guardrail_identifier:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": self._settings.guardrail_identifier,
                "guardrailVersion": self._settings.guardrail_version,
                "trace": "enabled",
            }
        return kwargs

    def _default_inference_config(self, model_id: str) -> dict[str, Any]:
        thinking_on = is_claude_sonnet_5(model_id) and self._settings.thinking_type == "adaptive"
        max_tokens = (
            self._settings.max_tokens
            if is_claude_sonnet_5(model_id)
            else self._settings.fast_tier_max_tokens
        )
        config: dict[str, Any] = {"maxTokens": max_tokens}
        if not thinking_on:
            config["temperature"] = 0.2 if not is_claude_sonnet_5(model_id) else self._settings.temperature
        return config

    def _additional_model_request_fields(self, model_id: str) -> dict[str, Any] | None:
        if not is_claude_sonnet_5(model_id):
            return None
        if self._settings.thinking_type == "disabled":
            return {"thinking": {"type": "disabled"}}
        return {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self._settings.thinking_effort},
        }
