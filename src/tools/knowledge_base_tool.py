"""Amazon Bedrock Knowledge Bases retrieval tool."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from tools.base import Tool


class KnowledgeBaseTool(Tool):
    name = "retrieve_knowledge"
    description = (
        "Semantically search the Amazon Bedrock Knowledge Base (OpenSearch Serverless). "
        "Use for policies, manuals, FAQs, and any fact that should be grounded in ingested "
        "S3 documents. Return passages with scores and source URIs."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Focused natural-language retrieval query.",
            },
            "number_of_results": {
                "type": "integer",
                "description": "How many passages to return (1-10). Default from configuration.",
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        region: str,
        knowledge_base_id: str,
        default_results: int = 5,
        client: Any | None = None,
    ) -> None:
        self._knowledge_base_id = knowledge_base_id
        self._default_results = default_results
        self._client = client or boto3.client(
            "bedrock-agent-runtime",
            region_name=region,
            config=Config(retries={"mode": "adaptive"}),
        )

    def invoke(self, tool_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if not self._knowledge_base_id:
            return {"error": "Knowledge base is not configured", "results": []}
        query = (tool_input.get("query") or "").strip()
        if not query:
            raise ValueError("retrieve_knowledge requires a query")
        n = int(tool_input.get("number_of_results") or self._default_results)
        n = max(1, min(n, 10))
        response = self._client.retrieve(
            knowledgeBaseId=self._knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": n}
            },
        )
        results = []
        for item in response.get("retrievalResults", []):
            loc = item.get("location", {})
            s3 = loc.get("s3Location") or {}
            results.append(
                {
                    "content": (item.get("content") or {}).get("text", ""),
                    "score": item.get("score"),
                    "uri": s3.get("uri") or loc.get("type"),
                    "location": loc,
                }
            )
        return {"query": query, "results": results}
