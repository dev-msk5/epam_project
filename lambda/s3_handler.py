# AWS Lambda, runs independently of the API, triggered by S3 ObjectCreated events
"""
Triggered on S3 ObjectCreated events
Parses project_id from key: projects/{project_id}/documents/...
Sums all object sizes under that project prefix
Enforces PROJECT_STORAGE_LIMIT_BYTES by deleting the offending file if exceeded
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
LIMIT_BYTES = int(os.environ.get(
    "PROJECT_STORAGE_LIMIT_BYTES", 524_288_000))  # 500 MB

KEY_RE = re.compile(r"^projects/(?P<project_id>\d+)/documents/")


def _parse_project_id(key: str) -> int | None:
    """Parse project_id from S3 key. Returns None if key does not match expected pattern"""
    m = KEY_RE.match(key)
    return int(m.group("project_id")) if m else None


def _sum_project_size(project_id: int) -> int:
    """Page through all S3 objects under projects/{project_id}/documents/ and sum sizes"""
    prefix = f"projects/{project_id}/documents/"
    total = 0
    paginator = S3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            total += obj["Size"]
    return total


def handler(event, context):
    """AWS Lambda entry point for S3 ObjectCreated events"""
    for record in event.get("Records", []):
        key = record["s3"]["object"]["key"]
        project_id = _parse_project_id(key)

        if project_id is None:
            log.warning("Unrecognised key pattern, skipping: %s", key)
            continue

        try:
            total = _sum_project_size(project_id)
        except Exception as exc:
            log.error(
                "Failed to calculate storage for project_id=%s: %s",
                project_id,
                exc,
            )
            continue

        log.info("project_id=%s total_storage=%s bytes", project_id, total)

        if total > LIMIT_BYTES:
            log.warning(
                "project_id=%s exceeded quota: %s > %s bytes — deleting offending file: %s",
                project_id,
                total,
                LIMIT_BYTES,
                key,
            )
            try:
                S3.delete_object(Bucket=BUCKET, Key=key)
                log.info("Deleted offending file: %s", key)
            except Exception as exc:
                log.error("Failed to delete offending file %s: %s", key, exc)

    return {"statusCode": 200}
