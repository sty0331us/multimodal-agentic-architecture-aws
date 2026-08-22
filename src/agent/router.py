"""Model router for Multimodal Agentic Architecture on AWS (Haiku fast / Sonnet 5 reasoning)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from agent.schemas import QueryRequest
from observability.logger import get_logger
from settings import Settings

logger = get_logger(__name__)

Tier = Literal["fast", "reasoning"]
RouterSource = Literal["heuristic", "llm", "override", "forced"]

_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank you",
    "thx",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "what's up",
    "whats up",
    "yo",
    "ok",
    "okay",
}

_REASONING_HINTS = (
    "analyze",
    "analyse",
    "compare",
    "refactor",
    "implement",
    "architecture",
    "step by step",
    "multi-hop",
    "tradeoff",
    "trade-off",
    "debug",
    "why does",
    "how should we",
    "design a",
    "write a function",
    "write code",
    "python",
    "typescript",
    "cdk",
    "lambda",
    "compliance",
    "synthesize",
    "plan the",
    "root cause",
    "evaluate",
    "assess this",
    "across documents",
    "according to our",
    "cite",
)

_FAST_HINTS = (
    "what is",
    "what's",
    "who is",
    "define",
    "when is",
    "summarize this in one",
    "one sentence",
    "quick summary",
    "faq",
)

_CODE_RE = re.compile(
    r"```|def |class |function |import |select |from src/|refactor|unit test",
    re.IGNORECASE,
)

CLASSIFIER_SYSTEM = (
    "You are a routing classifier for a dual-tier AWS agent. "
    "Reply with JSON only, no markdown: "
    '{"tier":"fast"|"reasoning","confidence":0.0-1.0,"reason":"short"}. '
    "fast = greetings, chit-chat, simple FAQ, one-shot fact lookup, tiny summaries. "
    "reasoning = code, multimodal/image analysis, multi-hop RAG, planning, deep comparison."
)


@dataclass(frozen=True)
class ModelTierDecision:
    tier: Tier
    model_id: str
    reason: str
    source: RouterSource
    confidence: float

    @property
    def is_reasoning(self) -> bool:
        return self.tier == "reasoning"


class ModelRouter:
    """Heuristic-first router with optional Haiku classification on ambiguous queries."""

    def __init__(self, settings: Settings, classifier: Any | None = None) -> None:
        self._settings = settings
        self._classifier = classifier

    def decide(self, request: QueryRequest) -> ModelTierDecision:
        override = (request.metadata or {}).get("model_tier", "").strip().lower()
        if override in {"fast", "reasoning"}:
            return self._decision(override, "client metadata override", "override", 1.0)

        mode = self._settings.router_mode
        if mode == "reasoning_only":
            return self._decision("reasoning", "ROUTER_MODE=reasoning_only", "forced", 1.0)
        if mode == "fast_only":
            return self._decision("fast", "ROUTER_MODE=fast_only", "forced", 1.0)

        heuristic = bind_model_ids(classify_complexity(request), self._settings)
        if mode == "heuristic" or heuristic.confidence >= self._settings.router_confidence_floor:
            return heuristic

        llm = self._classify_with_fast_tier(request)
        if llm:
            return llm
        return heuristic

    def _classify_with_fast_tier(self, request: QueryRequest) -> ModelTierDecision | None:
        if self._classifier is None:
            return None
        try:
            response = self._classifier.converse(
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": f"Query: {request.query[:1500]}\nHas image: {request.has_image}"}],
                    }
                ],
                system=[{"text": CLASSIFIER_SYSTEM}],
                model_id=self._settings.fast_tier_model_id,
                inference_config={"maxTokens": 80, "temperature": 0},
            )
        except Exception:
            logger.exception("router_llm_classifier_failed")
            return None
        text = _first_text(response)
        parsed = _parse_classifier_json(text)
        if not parsed:
            logger.info("router_llm_unparsed", extra={"raw": text[:200]})
            return None
        tier: Tier = parsed["tier"]
        confidence = float(parsed.get("confidence") or 0.7)
        reason = str(parsed.get("reason") or "llm classifier")
        logger.info(
            "router_llm_decision",
            extra={"tier": tier, "confidence": confidence, "reason": reason},
        )
        return self._decision(tier, f"llm:{reason}", "llm", confidence)

    def _decision(
        self, tier: str, reason: str, source: RouterSource, confidence: float
    ) -> ModelTierDecision:
        model_id = (
            self._settings.fast_tier_model_id
            if tier == "fast"
            else self._settings.resolved_reasoning_model_id
        )
        return ModelTierDecision(
            tier=tier,  # type: ignore[arg-type]
            model_id=model_id,
            reason=reason,
            source=source,
            confidence=confidence,
        )


def classify_complexity(request: QueryRequest) -> ModelTierDecision:
    """Deterministic, zero-cost complexity score used before any Bedrock call."""
    query = request.query.strip()
    lowered = query.lower()
    words = lowered.split()

    if request.has_image:
        return _heuristic("reasoning", "multimodal image attached", 0.97)
    if _CODE_RE.search(query):
        return _heuristic("reasoning", "code or refactoring intent", 0.93)
    if any(hint in lowered for hint in _REASONING_HINTS):
        return _heuristic("reasoning", "complex reasoning / multi-hop language", 0.88)
    if lowered.count("?") >= 2 or len(query) > 480 or len(words) > 80:
        return _heuristic("reasoning", "long or multi-question prompt", 0.78)

    compact = re.sub(r"[^a-z\s']", "", lowered).strip()
    if compact in _GREETINGS or (len(words) <= 6 and any(compact.startswith(g) for g in _GREETINGS)):
        return _heuristic("fast", "greeting or casual chit-chat", 0.96)
    if len(words) <= 14 and any(lowered.startswith(h) or f" {h} " in f" {lowered} " for h in _FAST_HINTS):
        return _heuristic("fast", "simple FAQ / one-shot lookup", 0.84)
    if len(words) <= 8:
        return _heuristic("fast", "short prompt", 0.72)
    return _heuristic("reasoning", "ambiguous length — prefer reasoning", 0.55)


def _heuristic(tier: Tier, reason: str, confidence: float) -> ModelTierDecision:
    return ModelTierDecision(
        tier=tier,
        model_id="",
        reason=reason,
        source="heuristic",
        confidence=confidence,
    )


def bind_model_ids(decision: ModelTierDecision, settings: Settings) -> ModelTierDecision:
    """Fill model_id after a pure heuristic (used by the router and tests)."""
    model_id = (
        settings.fast_tier_model_id
        if decision.tier == "fast"
        else settings.resolved_reasoning_model_id
    )
    return ModelTierDecision(
        tier=decision.tier,
        model_id=model_id,
        reason=decision.reason,
        source=decision.source,
        confidence=decision.confidence,
    )


def _first_text(response: dict[str, Any]) -> str:
    message = response.get("output", {}).get("message") or {}
    parts: list[str] = []
    for block in message.get("content") or []:
        if "text" in block:
            parts.append(block["text"])
    return "\n".join(parts).strip()


def _parse_classifier_json(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    tier = str(data.get("tier") or "").lower()
    if tier not in {"fast", "reasoning"}:
        return None
    data["tier"] = tier
    return data
