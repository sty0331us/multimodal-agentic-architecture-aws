"""Agent orchestrator for Multimodal Agentic Architecture on AWS (Haiku fast / Sonnet 5 reasoning)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from agent.converse import BedrockConverseClient
from agent.prompts import build_system_prompt
from agent.router import ModelRouter, ModelTierDecision
from agent.routing import classify_query
from agent.schemas import Citation, QueryRequest, QueryResponse, ToolTrace
from observability.logger import get_logger, metrics
from settings import Settings
from tools.base import Tool, tool_config_from
from tools.knowledge_base_tool import KnowledgeBaseTool
from tools.rekognition_tool import RekognitionTool
from utils.images import ResolvedImage, resolve_image
from utils.s3 import S3Service

logger = get_logger(__name__)

_LOW_CONFIDENCE_MARKERS = (
    "i don't know",
    "i do not know",
    "not sure",
    "cannot determine",
    "i'm not confident",
    "insufficient information",
)


class AgentOrchestrator:
    def __init__(
        self,
        settings: Settings,
        *,
        converse: BedrockConverseClient | None = None,
        s3: S3Service | None = None,
        tools: list[Tool] | None = None,
        router: ModelRouter | None = None,
    ) -> None:
        self._settings = settings
        self._converse = converse or BedrockConverseClient(settings)
        self._s3 = s3 or S3Service(settings)
        self._tools = tools or [
            RekognitionTool(region=settings.aws_region),
            KnowledgeBaseTool(
                region=settings.aws_region,
                knowledge_base_id=settings.knowledge_base_id,
                default_results=settings.kb_number_of_results,
            ),
        ]
        self._tool_by_name = {tool.name: tool for tool in self._tools}
        self._router = router or ModelRouter(settings, classifier=self._converse)

    def run(self, request: QueryRequest) -> QueryResponse:
        started = time.perf_counter()
        session_id = request.session_id or str(uuid.uuid4())
        modality = classify_query(request)
        decision = self._router.decide(request)
        image = resolve_image(request, self._s3.get_bytes)
        logger.info(
            "agent_run_start",
            extra={
                "session_id": session_id,
                "modality": modality.modality,
                "model_tier": decision.tier,
                "model_id": decision.model_id,
                "router_reason": decision.reason,
                "router_source": decision.source,
                "router_confidence": decision.confidence,
            },
        )
        metrics.add_metric(name="AgentInvocations", unit="Count", value=1)
        self._emit_tier_metric(decision.tier)

        user_content = self._user_content(request, image, modality.suggest_rekognition)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]
        traces: list[ToolTrace] = []
        citations: list[Citation] = []
        last_response: dict[str, Any] = {}
        usage_totals: dict[str, int] = {}
        model_id = decision.model_id
        context = {
            "image_bucket": image.bucket if image else None,
            "image_key": image.key if image else None,
            "image_bytes": image.data if image and not image.bucket else None,
        }

        for iteration in range(self._settings.max_tool_iterations):
            last_response = self._converse.converse(
                messages=messages,
                system=[{"text": build_system_prompt()}],
                tool_config=tool_config_from(self._tools),
                model_id=model_id,
            )
            _accumulate_usage(usage_totals, last_response.get("usage") or {})
            stop = last_response.get("stopReason")
            output_message = last_response.get("output", {}).get("message") or {
                "role": "assistant",
                "content": [],
            }
            if stop == "guardrail_intervened":
                metrics.add_metric(name="GuardrailInterventions", unit="Count", value=1)
                return self._finalize(
                    last_response,
                    session_id,
                    traces,
                    citations,
                    decision,
                    model_id,
                    usage_totals,
                    started,
                    fallback="The safety guardrail blocked this turn. Please rephrase.",
                )

            if stop == "tool_use" and decision.tier == "fast" and self._should_escalate(
                output_message.get("content") or [], iteration
            ):
                model_id, decision = self._escalate(decision, "complex or multi-step tool use")
                continue

            if stop != "tool_use":
                answer = _extract_text(last_response)
                if (
                    decision.tier == "fast"
                    and self._settings.router_escalate_on_tools
                    and _looks_low_confidence(answer)
                ):
                    model_id, decision = self._escalate(decision, "low-confidence fast-tier answer")
                    continue
                latency_ms = _elapsed_ms(started)
                logger.info(
                    "agent_run_complete",
                    extra={
                        "iterations": iteration + 1,
                        "stop": stop,
                        "model_tier": decision.tier,
                        "model_id": model_id,
                        "latency_ms": latency_ms,
                        "usage": usage_totals,
                    },
                )
                self._collect_citations_from_traces(traces, citations)
                return self._finalize(
                    last_response,
                    session_id,
                    traces,
                    citations,
                    decision,
                    model_id,
                    usage_totals,
                    started,
                )

            messages.append(output_message)
            tool_results, new_traces, new_citations = self._execute_tools(
                output_message.get("content") or [], context
            )
            traces.extend(new_traces)
            citations.extend(new_citations)
            messages.append({"role": "user", "content": tool_results})

        metrics.add_metric(name="AgentMaxIterations", unit="Count", value=1)
        return self._finalize(
            last_response,
            session_id,
            traces,
            citations,
            decision,
            model_id,
            usage_totals,
            started,
            fallback="Reached the tool-iteration limit before a final answer.",
        )

    def _should_escalate(self, content: list[dict[str, Any]], iteration: int) -> bool:
        if not self._settings.router_escalate_on_tools:
            return False
        names = [block.get("toolUse", {}).get("name") for block in content if block.get("toolUse")]
        if "analyze_image" in names:
            return True
        if iteration >= 1:
            return True
        return len(names) > 1

    def _escalate(
        self, current: ModelTierDecision, reason: str
    ) -> tuple[str, ModelTierDecision]:
        metrics.add_metric(name="RouterEscalations", unit="Count", value=1)
        self._emit_tier_metric("reasoning")
        upgraded = ModelTierDecision(
            tier="reasoning",
            model_id=self._settings.resolved_reasoning_model_id,
            reason=f"escalation:{reason}",
            source="forced",
            confidence=1.0,
        )
        logger.info(
            "router_escalation",
            extra={
                "from_tier": current.tier,
                "from_model": current.model_id,
                "to_model": upgraded.model_id,
                "reason": reason,
            },
        )
        return upgraded.model_id, upgraded

    def _user_content(
        self, request: QueryRequest, image: ResolvedImage | None, suggest_rekognition: bool
    ) -> list[dict[str, Any]]:
        hint = ""
        if suggest_rekognition and image:
            hint = (
                "\n\nAn image is attached. Call analyze_image if structured vision "
                "signals would improve the answer, then retrieve_knowledge if documents apply."
            )
        blocks: list[dict[str, Any]] = []
        if image:
            blocks.append({"image": {"format": image.fmt, "source": {"bytes": image.data}}})
        blocks.append({"text": request.query + hint})
        return blocks

    def _execute_tools(
        self, content: list[dict[str, Any]], context: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[ToolTrace], list[Citation]]:
        tool_results: list[dict[str, Any]] = []
        traces: list[ToolTrace] = []
        citations: list[Citation] = []
        for block in content:
            tool_use = block.get("toolUse")
            if not tool_use:
                continue
            name = tool_use["name"]
            tool_use_id = tool_use["toolUseId"]
            tool_input = tool_use.get("input") or {}
            tool = self._tool_by_name.get(name)
            try:
                if tool is None:
                    raise ValueError(f"Unknown tool: {name}")
                result = tool.invoke(tool_input, context)
                status = "success"
                metrics.add_metric(name="ToolSuccess", unit="Count", value=1)
            except Exception as exc:  # noqa: BLE001
                logger.exception("tool_invoke_failed", extra={"tool": name})
                result = {"error": str(exc)}
                status = "error"
                metrics.add_metric(name="ToolErrors", unit="Count", value=1)
            preview = json.dumps(result, default=str)[:1500]
            traces.append(
                ToolTrace(name=name, input=tool_input, output_preview=preview, status=status)
            )
            if name == "retrieve_knowledge" and status == "success":
                for item in result.get("results") or []:
                    citations.append(
                        Citation(
                            source=item.get("uri") or "knowledge-base",
                            score=item.get("score"),
                            excerpt=(item.get("content") or "")[:500],
                            location=item.get("location") or {},
                        )
                    )
            tool_results.append(
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": result}],
                        "status": "success" if status == "success" else "error",
                    }
                }
            )
        return tool_results, traces, citations

    @staticmethod
    def _collect_citations_from_traces(traces: list[ToolTrace], citations: list[Citation]) -> None:
        _ = traces, citations

    def _finalize(
        self,
        response: dict[str, Any],
        session_id: str,
        traces: list[ToolTrace],
        citations: list[Citation],
        decision: ModelTierDecision,
        model_id: str,
        usage_totals: dict[str, int],
        started: float,
        fallback: str | None = None,
    ) -> QueryResponse:
        text = _extract_text(response) or fallback or ""
        latency_ms = _elapsed_ms(started)
        metrics.add_metric(name="AgentLatencyMs", unit="Milliseconds", value=latency_ms)
        if usage_totals.get("inputTokens"):
            metrics.add_metric(
                name="InputTokens", unit="Count", value=usage_totals["inputTokens"]
            )
        if usage_totals.get("outputTokens"):
            metrics.add_metric(
                name="OutputTokens", unit="Count", value=usage_totals["outputTokens"]
            )
        guardrail = None
        trace = response.get("trace") or {}
        if "guardrail" in trace:
            guardrail = str(trace["guardrail"].get("action") or "intervened")
        return QueryResponse(
            answer=text,
            session_id=session_id,
            stop_reason=response.get("stopReason") or "end_turn",
            model_id=model_id,
            model_tier=decision.tier,
            router_reason=decision.reason,
            router_source=decision.source,
            latency_ms=latency_ms,
            citations=citations,
            tool_trace=traces,
            guardrail_action=guardrail,
            usage=usage_totals,
        )

    @staticmethod
    def _emit_tier_metric(tier: str) -> None:
        name = "ModelTierFast" if tier == "fast" else "ModelTierReasoning"
        metrics.add_metric(name=name, unit="Count", value=1)


def _extract_text(response: dict[str, Any]) -> str:
    message = response.get("output", {}).get("message") or {}
    parts: list[str] = []
    for block in message.get("content") or []:
        if "text" in block:
            parts.append(block["text"])
    return "\n".join(parts).strip()


def _looks_low_confidence(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _LOW_CONFIDENCE_MARKERS)


def _accumulate_usage(totals: dict[str, int], usage: dict[str, Any]) -> None:
    for key, value in usage.items():
        if isinstance(value, (int, float)):
            totals[key] = totals.get(key, 0) + int(value)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
