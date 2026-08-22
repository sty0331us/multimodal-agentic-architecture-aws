"""Agent loop with a fake Bedrock Converse client."""

from __future__ import annotations

from agent.orchestrator import AgentOrchestrator
from agent.schemas import QueryRequest
from settings import Settings
from tools.base import Tool


class FakeConverse:
    def __init__(self) -> None:
        self.calls = 0

    def converse(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "stopReason": "tool_use",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "tool-1",
                                    "name": "retrieve_knowledge",
                                    "input": {"query": "ppe policy"},
                                }
                            }
                        ],
                    }
                },
                "usage": {"inputTokens": 10, "outputTokens": 5},
            }
        return {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hard hats are required in zone A. Sources: s3://docs/ppe.md"}],
                }
            },
            "usage": {"inputTokens": 20, "outputTokens": 40},
        }


class FakeRetrieve(Tool):
    name = "retrieve_knowledge"
    description = "fake"
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}

    def invoke(self, tool_input, context):
        return {
            "query": tool_input["query"],
            "results": [
                {
                    "content": "Hard hats are required in zone A.",
                    "score": 0.91,
                    "uri": "s3://docs/ppe.md",
                    "location": {},
                }
            ],
        }


class FakeS3:
    def get_bytes(self, bucket: str, key: str) -> bytes:
        raise AssertionError("S3 should not be called for text-only tests")


def test_tool_loop_returns_grounded_answer(monkeypatch) -> None:
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    settings = Settings()
    orch = AgentOrchestrator(
        settings,
        converse=FakeConverse(),
        s3=FakeS3(),
        tools=[FakeRetrieve()],
    )
    result = orch.run(QueryRequest(query="What is the PPE policy?"))
    assert "Hard hats" in result.answer
    assert result.citations[0].source == "s3://docs/ppe.md"
    assert result.tool_trace[0].name == "retrieve_knowledge"
    assert result.stop_reason == "end_turn"
    assert result.model_tier == "fast"
    assert result.latency_ms is not None
