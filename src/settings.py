"""Lambda-safe environment configuration for Multimodal Agentic Architecture on AWS."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from models import DEFAULT_FAST_TIER_MODEL_ID, DEFAULT_REASONING_TIER_MODEL_ID


class Settings(BaseSettings):
    """Environment-driven settings for Lambda handlers and local scripts."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    powertools_service_name: str = Field(
        default="multimodal-agentic-architecture-aws", alias="POWERTOOLS_SERVICE_NAME"
    )
    powertools_metrics_namespace: str = Field(
        default="MultimodalAgenticArchitectureAws", alias="POWERTOOLS_METRICS_NAMESPACE"
    )

    fast_tier_model_id: str = Field(
        default=DEFAULT_FAST_TIER_MODEL_ID,
        alias="FAST_TIER_MODEL_ID",
    )
    reasoning_tier_model_id: str = Field(
        default=DEFAULT_REASONING_TIER_MODEL_ID,
        alias="REASONING_TIER_MODEL_ID",
    )
    # Optional override: if set, used as the reasoning-tier model id.
    bedrock_model_id: str = Field(default="", alias="BEDROCK_MODEL_ID")

    router_mode: Literal["heuristic", "hybrid", "reasoning_only", "fast_only"] = Field(
        default="hybrid", alias="ROUTER_MODE"
    )
    router_escalate_on_tools: bool = Field(default=True, alias="ROUTER_ESCALATE_ON_TOOLS")
    router_confidence_floor: float = Field(default=0.62, alias="ROUTER_CONFIDENCE_FLOOR")

    knowledge_base_id: str = Field(default="", alias="KNOWLEDGE_BASE_ID")
    guardrail_identifier: str = Field(default="", alias="GUARDRAIL_IDENTIFIER")
    guardrail_version: str = Field(default="DRAFT", alias="GUARDRAIL_VERSION")

    uploads_bucket: str = Field(default="", alias="UPLOADS_BUCKET")
    documents_bucket: str = Field(default="", alias="DOCUMENTS_BUCKET")
    documents_prefix: str = Field(default="knowledge/", alias="DOCUMENTS_PREFIX")
    data_source_id: str = Field(default="", alias="DATA_SOURCE_ID")

    max_tool_iterations: int = Field(default=6, alias="MAX_TOOL_ITERATIONS")
    max_tokens: int = Field(default=8192, alias="MAX_TOKENS")
    fast_tier_max_tokens: int = Field(default=1024, alias="FAST_TIER_MAX_TOKENS")
    temperature: float = Field(default=1.0, alias="TEMPERATURE")
    thinking_type: Literal["adaptive", "disabled"] = Field(
        default="adaptive", alias="THINKING_TYPE"
    )
    thinking_effort: Literal["low", "medium", "high", "xhigh", "max"] = Field(
        default="medium", alias="THINKING_EFFORT"
    )
    kb_number_of_results: int = Field(default=5, alias="KB_NUMBER_OF_RESULTS")

    api_base_url: str = Field(default="", alias="API_BASE_URL")
    presign_expires_seconds: int = Field(default=900, alias="PRESIGN_EXPIRES_SECONDS")
    kms_key_id: str = Field(default="", alias="KMS_KEY_ID")

    @property
    def resolved_reasoning_model_id(self) -> str:
        return self.bedrock_model_id or self.reasoning_tier_model_id


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
