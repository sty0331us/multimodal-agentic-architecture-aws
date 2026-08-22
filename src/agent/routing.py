"""Multimodal routing: decide how text and images enter the agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent.schemas import QueryRequest

Modality = Literal["text", "image", "multimodal"]


@dataclass(frozen=True)
class RouteDecision:
    modality: Modality
    use_vision_model: bool
    suggest_rekognition: bool
    suggest_retrieval: bool


def classify_query(request: QueryRequest) -> RouteDecision:
    """Route a request without calling AWS.

    Claude Sonnet 5 still chooses tools; this only hints vision vs retrieval.
    """
    has_image = request.has_image
    text = request.query.lower()
    retrieval_hints = (
        "policy",
        "document",
        "manual",
        "according to",
        "knowledge",
        "our ",
        "handbook",
        "sop",
        "procedure",
        "cite",
        "source",
    )
    suggest_retrieval = any(hint in text for hint in retrieval_hints) or not has_image
    if has_image and request.query.strip():
        modality: Modality = "multimodal"
    elif has_image:
        modality = "image"
    else:
        modality = "text"
    return RouteDecision(
        modality=modality,
        use_vision_model=has_image,
        suggest_rekognition=has_image,
        suggest_retrieval=suggest_retrieval,
    )
