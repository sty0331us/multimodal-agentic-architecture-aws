#!/usr/bin/env python3
"""Presign and upload a document into the Multimodal Agentic Architecture on AWS knowledge-base S3 prefix.

Example:
  python scripts/ingest_document.py samples/documents/ppe_policy.md
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--api-url", default=os.getenv("API_BASE_URL"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY"))
    args = parser.parse_args()
    if not args.api_url or not args.api_key:
        print("Set API_BASE_URL and API_KEY", file=sys.stderr)
        return 2

    path = Path(args.file)
    content_type = mimetypes.guess_type(path.name)[0] or "text/plain"
    presign_req = urllib.request.Request(
        args.api_url.rstrip("/") + "/v1/documents/presign",
        data=json.dumps({"filename": path.name, "content_type": content_type}).encode(),
        headers={"Content-Type": "application/json", "x-api-key": args.api_key},
        method="POST",
    )
    with urllib.request.urlopen(presign_req, timeout=30) as response:  # noqa: S310
        presign = json.loads(response.read().decode())

    put = urllib.request.Request(
        presign["url"],
        data=path.read_bytes(),
        headers=presign.get("headers") or {"Content-Type": content_type},
        method="PUT",
    )
    with urllib.request.urlopen(put, timeout=60) as response:  # noqa: S310
        if response.status not in {200, 201}:
            print(f"Upload failed: {response.status}", file=sys.stderr)
            return 1
    print(json.dumps({"uploaded": True, "bucket": presign["bucket"], "key": presign["key"]}, indent=2))
    print("Ingestion job starts from the S3 ObjectCreated event. Allow 1-3 minutes before querying.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
