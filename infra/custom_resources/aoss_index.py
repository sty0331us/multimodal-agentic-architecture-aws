"""CloudFormation custom resource: create the OpenSearch Serverless vector index."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    props = event.get("ResourceProperties") or {}
    request_type = event["RequestType"]
    endpoint = props["collectionEndpoint"].rstrip("/")
    index_name = props["indexName"]
    dimension = int(props.get("dimension") or 1024)
    region = os.environ.get("AWS_REGION") or os.environ["AWS_DEFAULT_REGION"]

    if request_type == "Delete":
        _signed("DELETE", f"{endpoint}/{index_name}", region=region)
        return {"PhysicalResourceId": index_name, "Data": {"indexName": index_name}}

    body = {
        "settings": {"index.knn": True},
        "mappings": {
            "properties": {
                "bedrock-knowledge-base-default-vector": {
                    "type": "knn_vector",
                    "dimension": dimension,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "space_type": "l2",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
                "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text"},
                "AMAZON_BEDROCK_METADATA": {"type": "text", "index": False},
            }
        },
    }
    status, payload = _signed("HEAD", f"{endpoint}/{index_name}", region=region)
    if status == 404:
        status, payload = _signed("PUT", f"{endpoint}/{index_name}", body=body, region=region)
        if status >= 400:
            raise RuntimeError(f"Failed to create index ({status}): {payload}")
    elif status >= 400 and status != 200:
        raise RuntimeError(f"Failed to describe index ({status}): {payload}")

    return {
        "PhysicalResourceId": index_name,
        "Data": {"indexName": index_name, "endpoint": endpoint},
    }


def _signed(
    method: str,
    url: str,
    *,
    region: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, str]:
    session = boto3.Session()
    creds = session.get_credentials()
    if creds is None:
        raise RuntimeError("No AWS credentials available for AOSS signing")
    frozen = creds.get_frozen_credentials()
    parsed = urlparse(url)
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"host": parsed.netloc}
    if data is not None:
        headers["content-type"] = "application/json"
    request = AWSRequest(method=method, url=url, data=data, headers=headers)
    SigV4Auth(frozen, "aoss", region).add_auth(request)
    prepared = request.prepare()
    req = urllib.request.Request(  # noqa: S310
        prepared.url,
        data=prepared.body,
        headers=dict(prepared.headers),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
