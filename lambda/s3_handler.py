# AWS Lambda — runs independently, not part of app
"""
Triggered on S3 ObjectCreated events.
Parses project_id from key: projects/{project_id}/documents/...
Sums all object sizes under that project prefix.
Logs a warning if the total exceeds PROJECT_STORAGE_LIMIT_BYTES.
"""

from __future__ import annotations

import logging
import os
import re

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

S3 = boto3.client("s3")
BUCKET = os.environ["S3_BUCKET_NAME"]
LIMIT_BYTES = int(
    os.environ.get("PROJECT_STORAGE_LIMIT_BYTES", 524288000)
)  # 500 MB default

KEY_RE = re.compile(r"^projects/(?P<project_id>\d+)/documents/")


def _parse_project_id(key: str) -> int | None:
    """Attempt to parse project_id from S3 key. Returns None if not found"""
    m = KEY_RE.match(key)  # m is a match object if the regex matches, otherwise None
    return int(m.group("project_id")) if m else None


def _sum_project_size(project_id: int) -> int:
    """Page through all S3 objects under projects/{project_id}/documents/ and sum sizes."""
    prefix = f"projects/{project_id}/documents/"
    total = 0
    paginator = S3.get_paginator("list_objects_v2")
    # pagiator returns a generator of pages, each page is a dict with "Contents" key
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            total += obj["Size"]
    return total


def handler(event, context):
    """AWS Lambda handler for S3 ObjectCreated events"""
    for record in event.get("Records", []):
        key = record["s3"]["object"]["key"]
        project_id = _parse_project_id(key)

        if project_id is None:
            log.warning("Unrecognised key pattern, skipping: %s", key)
            continue

        total = _sum_project_size(project_id)
        log.info("project_id=%s total_storage=%s bytes", project_id, total)

        if total > LIMIT_BYTES:
            log.warning(
                "project_id=%s exceeded quota: %s > %s bytes",
                project_id,
                total,
                LIMIT_BYTES,
            )

    return {"statusCode": 200}
