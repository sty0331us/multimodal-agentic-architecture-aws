#!/usr/bin/env python3
"""Fetch CloudFormation outputs for Multimodal Agentic Architecture on AWS and print shell exports."""

from __future__ import annotations

import argparse
import json
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack", default="MultimodalAgenticArchitectureStack")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    cmd = [
        "aws",
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        args.stack,
        "--region",
        args.region,
        "--query",
        "Stacks[0].Outputs",
        "--output",
        "json",
    ]
    raw = subprocess.check_output(cmd, text=True)
    outputs = {item["OutputKey"]: item["OutputValue"] for item in json.loads(raw)}
    mapping = {
        "ApiUrl": "API_BASE_URL",
        "KnowledgeBaseId": "KNOWLEDGE_BASE_ID",
        "GuardrailId": "GUARDRAIL_IDENTIFIER",
        "GuardrailVersion": "GUARDRAIL_VERSION",
        "DocumentsBucket": "DOCUMENTS_BUCKET",
        "UploadsBucket": "UPLOADS_BUCKET",
        "DataSourceId": "DATA_SOURCE_ID",
    }
    for cfn_key, env_key in mapping.items():
        if cfn_key in outputs:
            print(f"export {env_key}={outputs[cfn_key]}")
    if "ApiKeyId" in outputs:
        key_id = outputs["ApiKeyId"]
        value = subprocess.check_output(
            [
                "aws",
                "apigateway",
                "get-api-key",
                "--api-key",
                key_id,
                "--include-value",
                "--query",
                "value",
                "--output",
                "text",
                "--region",
                args.region,
            ],
            text=True,
        ).strip()
        print(f"export API_KEY={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
