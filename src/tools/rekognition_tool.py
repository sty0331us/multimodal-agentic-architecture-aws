"""Amazon Rekognition tool: labels, text, faces, and moderation."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from tools.base import Tool


class RekognitionTool(Tool):
    name = "analyze_image"
    description = (
        "Run Amazon Rekognition on the user-provided image. Returns object labels, "
        "detected text (OCR), face counts/attributes (no identification), and "
        "content-moderation labels. Use when an image is attached or when the user "
        "asks what is in a photo."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "bucket": {"type": "string", "description": "S3 bucket of the image, if known."},
            "key": {"type": "string", "description": "S3 object key of the image, if known."},
            "min_confidence": {
                "type": "number",
                "description": "Minimum confidence 0-100. Default 70.",
            },
        },
        "required": [],
    }

    def __init__(self, region: str, client: Any | None = None) -> None:
        self._client = client or boto3.client(
            "rekognition", region_name=region, config=Config(retries={"mode": "adaptive"})
        )

    def invoke(self, tool_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        image = self._image_payload(tool_input, context)
        min_conf = float(tool_input.get("min_confidence") or 70)
        labels = self._client.detect_labels(
            Image=image, MaxLabels=25, MinConfidence=min_conf
        )
        text = self._client.detect_text(Image=image)
        faces = self._client.detect_faces(Image=image, Attributes=["DEFAULT"])
        moderation = self._client.detect_moderation_labels(
            Image=image, MinConfidence=min_conf
        )
        return {
            "labels": [
                {"name": item["Name"], "confidence": round(item["Confidence"], 2)}
                for item in labels.get("Labels", [])
            ],
            "text_detections": [
                item["DetectedText"]
                for item in text.get("TextDetections", [])
                if item.get("Type") == "LINE"
            ],
            "face_count": len(faces.get("FaceDetails", [])),
            "faces": [
                {
                    "confidence": round(face.get("Confidence", 0), 2),
                    "emotions": [
                        e["Type"]
                        for e in face.get("Emotions", [])
                        if e.get("Confidence", 0) >= min_conf
                    ][:3],
                }
                for face in faces.get("FaceDetails", [])
            ],
            "moderation_labels": [
                {"name": item["Name"], "confidence": round(item["Confidence"], 2)}
                for item in moderation.get("ModerationLabels", [])
            ],
        }

    def _image_payload(self, tool_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        bucket = tool_input.get("bucket") or context.get("image_bucket")
        key = tool_input.get("key") or context.get("image_key")
        if bucket and key:
            return {"S3Object": {"Bucket": bucket, "Name": key}}
        image_bytes = context.get("image_bytes")
        if image_bytes:
            return {"Bytes": image_bytes}
        raise ValueError("No image available. Provide bucket/key or attach an image.")
