"""Pydantic contracts for the query API and agent runtime."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ImageRef(BaseModel):
    """Pointer to an image already stored in S3 (preferred over inline bytes)."""

    bucket: str
    key: str


class QueryRequest(BaseModel):
    """Multimodal user query accepted by POST /v1/query."""

    query: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=128)
    image: ImageRef | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    image_base64: str | None = Field(default=None, max_length=6_000_000)
    image_format: Literal["png", "jpeg", "gif", "webp"] | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _at_most_one_image_source(self) -> QueryRequest:
        sources = [self.image is not None, bool(self.image_url), bool(self.image_base64)]
        if sum(sources) > 1:
            raise ValueError("Provide only one of image, image_url, or image_base64")
        return self

    @property
    def has_image(self) -> bool:
        return any([self.image is not None, self.image_url, self.image_base64])


class Citation(BaseModel):
    source: str
    score: float | None = None
    excerpt: str | None = None
    location: dict[str, Any] = Field(default_factory=dict)


class ToolTrace(BaseModel):
    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output_preview: str = ""
    status: Literal["success", "error"] = "success"


class QueryResponse(BaseModel):
    answer: str
    session_id: str | None = None
    stop_reason: str
    model_id: str
    model_tier: Literal["fast", "reasoning"] | None = None
    router_reason: str | None = None
    router_source: str | None = None
    latency_ms: int | None = None
    citations: list[Citation] = Field(default_factory=list)
    tool_trace: list[ToolTrace] = Field(default_factory=list)
    guardrail_action: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)


class PresignRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=512)
    content_type: str = Field(default="application/octet-stream", max_length=128)
    purpose: Literal["upload", "document"] = "upload"


class PresignResponse(BaseModel):
    bucket: str
    key: str
    url: str
    expires_in: int
    headers: dict[str, str] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
