"""Routing classification tests."""

from __future__ import annotations

from agent.routing import classify_query
from agent.schemas import QueryRequest


def test_text_query_suggests_retrieval() -> None:
    decision = classify_query(QueryRequest(query="Summarize the onboarding handbook"))
    assert decision.modality == "text"
    assert decision.suggest_retrieval is True
    assert decision.use_vision_model is False


def test_multimodal_query() -> None:
    decision = classify_query(
        QueryRequest(query="Is this helmet compliant with policy?", image_url="https://example.com/h.jpg")
    )
    assert decision.modality == "multimodal"
    assert decision.suggest_rekognition is True
    assert decision.use_vision_model is True
