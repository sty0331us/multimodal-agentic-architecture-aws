"""Tool protocol and Converse tool-spec helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    def spec(self) -> dict[str, Any]:
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.description,
                "inputSchema": {"json": self.input_schema},
            }
        }

    @abstractmethod
    def invoke(self, tool_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


def tool_config_from(tools: list[Tool]) -> dict[str, Any]:
    # auto is required for Claude Sonnet 5 adaptive thinking (forced tool_use is rejected).
    return {"tools": [tool.spec() for tool in tools], "toolChoice": {"auto": {}}}
