#!/usr/bin/env python3
"""Call POST /v1/query against a deployed Multimodal Agentic Architecture on AWS API.

Examples:
  python scripts/test_query.py --query "What is the PPE policy?"
  python scripts/test_query.py --query "Is this PPE compliant?" --image samples/images/helmet.png
  python scripts/test_query.py --query "Describe this" --s3-bucket $UPLOADS_BUCKET --s3-key uploads/demo.png
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a multimodal query to the agent API")
    parser.add_argument("--query", required=True)
    parser.add_argument("--api-url", default=os.getenv("API_BASE_URL"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY"))
    parser.add_argument("--image", help="Local image file to send as base64")
    parser.add_argument("--image-url")
    parser.add_argument("--s3-bucket")
    parser.add_argument("--s3-key")
    args = parser.parse_args()
    if not args.api_url or not args.api_key:
        print("Set API_BASE_URL and API_KEY (or pass --api-url / --api-key)", file=sys.stderr)
        return 2

    body: dict = {"query": args.query}
    if args.image:
        data = Path(args.image).read_bytes()
        body["image_base64"] = base64.b64encode(data).decode()
        suffix = Path(args.image).suffix.lower().lstrip(".")
        body["image_format"] = "jpeg" if suffix in {"jpg", "jpeg"} else suffix or "png"
    if args.image_url:
        body["image_url"] = args.image_url
    if args.s3_bucket and args.s3_key:
        body["image"] = {"bucket": args.s3_bucket, "key": args.s3_key}

    url = args.api_url.rstrip("/") + "/v1/query"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": args.api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
