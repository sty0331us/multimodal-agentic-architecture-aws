"""Dual-tier model cascading: fast (Claude 4.5 Haiku) vs reasoning (Claude Sonnet 5)."""

from __future__ import annotations

from agent.router import ModelRouter, classify_complexity
from agent.schemas import QueryRequest
from models import DEFAULT_FAST_TIER_MODEL_ID, DEFAULT_REASONING_TIER_MODEL_ID
from settings import Settings


def test_greetings_and_short_chitchat_go_to_fast() -> None:
    for query in ("hello", "Thanks!", "good morning", "hi there"):
        decision = classify_complexity(QueryRequest(query=query))
        assert decision.tier == "fast", query


def test_simple_faq_goes_to_fast() -> None:
    decision = classify_complexity(QueryRequest(query="What is the PPE policy?"))
    assert decision.tier == "fast"


def test_code_and_refactor_go_to_reasoning() -> None:
    decision = classify_complexity(
        QueryRequest(query="Write a Python function to parse the PPE policy markdown and unit test it.")
    )
    assert decision.tier == "reasoning"
    assert decision.confidence >= 0.9


def test_multimodal_image_goes_to_reasoning() -> None:
    decision = classify_complexity(
        QueryRequest(
            query="Is this helmet compliant?",
            image={"bucket": "uploads", "key": "helmet.png"},
        )
    )
    assert decision.tier == "reasoning"
    assert "multimodal" in decision.reason


def test_multi_hop_analysis_goes_to_reasoning() -> None:
    decision = classify_complexity(
        QueryRequest(query="Compare Zone A and Zone B PPE, analyze gaps, and plan a rollout.")
    )
    assert decision.tier == "reasoning"


def test_router_binds_configured_model_ids() -> None:
    settings = Settings(router_mode="heuristic")
    router = ModelRouter(settings)
    assert DEFAULT_FAST_TIER_MODEL_ID == "anthropic.claude-haiku-4-5-20251001-v1:0"
    fast = router.decide(QueryRequest(query="hello"))
    assert fast.tier == "fast"
    assert fast.model_id == DEFAULT_FAST_TIER_MODEL_ID
    assert "claude-haiku-4-5" in fast.model_id
    hard = router.decide(
        QueryRequest(query="Refactor this CDK stack and design a multi-region architecture.")
    )
    assert hard.tier == "reasoning"
    assert hard.model_id == DEFAULT_REASONING_TIER_MODEL_ID


def test_metadata_override_forces_reasoning() -> None:
    settings = Settings(router_mode="heuristic")
    router = ModelRouter(settings)
    decision = router.decide(QueryRequest(query="hello", metadata={"model_tier": "reasoning"}))
    assert decision.tier == "reasoning"
    assert decision.source == "override"


def test_hybrid_uses_llm_when_heuristic_is_ambiguous() -> None:
    class FakeClassifier:
        def converse(self, **kwargs):
            assert kwargs["model_id"] == DEFAULT_FAST_TIER_MODEL_ID
            assert "claude-haiku-4-5" in kwargs["model_id"]
            assert kwargs["inference_config"]["maxTokens"] == 80
            assert kwargs["inference_config"]["temperature"] == 0
            return {
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"text": '{"tier":"fast","confidence":0.81,"reason":"simple ask"}'}
                        ],
                    }
                },
            }

    settings = Settings(router_mode="hybrid", router_confidence_floor=0.9)
    router = ModelRouter(settings, classifier=FakeClassifier())
    decision = router.decide(
        QueryRequest(query="Can you help me with the onboarding notes from last Thursday meeting please")
    )
    assert decision.source == "llm"
    assert decision.tier == "fast"
