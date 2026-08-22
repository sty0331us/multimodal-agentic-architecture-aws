"""Custom resource: create a scheduled Macie classification job."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    props = event.get("ResourceProperties") or {}
    request_type = event["RequestType"]
    client = boto3.client("macie2")
    name = props["jobName"]

    if request_type == "Delete":
        job_id = event.get("PhysicalResourceId") or ""
        if job_id and job_id != name:
            try:
                client.cancel_classification_job(jobId=job_id)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code not in {"ResourceNotFoundException", "ConflictException", "ValidationException"}:
                    raise
        return {"PhysicalResourceId": job_id or name}

    if request_type == "Create":
        response = client.create_classification_job(
            jobType="SCHEDULED",
            name=name,
            s3JobDefinition={
                "bucketDefinitions": [
                    {
                        "accountId": props["accountId"],
                        "buckets": props["buckets"],
                    }
                ]
            },
            scheduleFrequency={"dailySchedule": {}},
            description="Daily PII / sensitive-data scan for multimodal agent buckets",
        )
        job_id = response["jobId"]
        return {"PhysicalResourceId": job_id, "Data": {"jobId": job_id}}

    return {"PhysicalResourceId": event.get("PhysicalResourceId") or name}
