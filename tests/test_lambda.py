# Unit tests for lambda/s3_handler.py
#
# TestParseProjectId - covered cases:
#   valid key returns correct integer project_id
#   valid key with nested path under documents/ returns correct project_id
#   large numeric project_id is parsed correctly
#   wrong top-level prefix returns None
#   missing /documents/ segment returns None
#   non-numeric project_id returns None
#   empty string returns None
#   root-level key (no slashes) returns None
#   project_id of zero is parsed consistently
#
#
# TestHandler - covered cases:
#   always returns {"statusCode": 200}
#   unrecognised key pattern is skipped with WARNING log
#   empty Records list is handled without error
#   missing Records key is handled without error
#   total below limit - file is not deleted
#   total exactly at limit - file is not deleted (> not >=)
#   total above limit - offending file is deleted from S3
#   total above limit - only offending file deleted, other project files survive
#   _sum_project_size error is logged and handler continues to next record
#   delete_object failure is logged and handler still returns 200
#   multiple records from different projects are processed independently
from __future__ import annotations

import os

os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")  # nopep8 # noqa: E501
os.environ.setdefault("PROJECT_STORAGE_LIMIT_BYTES", "100")  # nopep8  # noqa: E501

from unittest.mock import MagicMock, patch

import boto3
import pytest
import s3_handler
from moto import mock_aws

BUCKET = "test-bucket"
LIMIT = 100


# Fixtures


@pytest.fixture(autouse=True)
def lambda_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the environment variables that the lambda expects to find"""
    monkeypatch.setenv("S3_BUCKET_NAME", BUCKET)
    monkeypatch.setenv("PROJECT_STORAGE_LIMIT_BYTES", str(LIMIT))


@pytest.fixture(autouse=True)
def reset_s3_singleton():
    """Force the lazy singleton to reinitialise for every test."""
    s3_handler.S3 = None
    yield
    s3_handler.S3 = None


@pytest.fixture()
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock AWS credentials for moto"""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture()
def s3_bucket(aws_credentials):
    """Create a mock S3 bucket for testing"""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def _put_object(client, key: str, size_bytes: int) -> None:
    """upload a fake object whose body is exactly *size_bytes* long"""
    client.put_object(Bucket=BUCKET, Key=key, Body=b"x" * size_bytes)


# _parse_project_id - pure logic, no AWS calls


class TestParseProjectId:
    """Covers every branch of the regex helper. Pure logic - no AWS calls"""

    def test_valid_key_returns_project_id(self):
        assert s3_handler._parse_project_id("projects/42/documents/report.pdf") == 42, (
            "project_id should be parsed correctly from a valid key"
        )

    def test_valid_key_with_nested_path(self):
        assert (
            s3_handler._parse_project_id("projects/7/documents/subdir/file.docx") == 7
        ), "project_id should be parsed correctly from a valid key with nested path"  # noqa: E501

    def test_large_project_id(self):
        assert (
            s3_handler._parse_project_id("projects/9999999/documents/x.pdf")
            == 9_999_999
        ), (
            "project_id should be parsed correctly from a valid key with a large numeric project_id"  # noqa: E501
        )

    def test_wrong_prefix_returns_none(self):
        assert s3_handler._parse_project_id("uploads/42/documents/file.pdf") is None, (
            "wrong top-level prefix should return None"
        )

    def test_missing_documents_segment_returns_none(self):
        assert s3_handler._parse_project_id("projects/42/file.pdf") is None, (
            "missing documents segment should return None"
        )

    def test_non_numeric_project_id_returns_none(self):
        assert (
            s3_handler._parse_project_id("projects/abc/documents/file.pdf") is None
        ), "non-numeric project_id should return None"

    def test_empty_string_returns_none(self):
        assert s3_handler._parse_project_id("") is None, (
            "empty string should return None"
        )

    def test_root_key_returns_none(self):
        assert s3_handler._parse_project_id("file.pdf") is None, (
            "root key should return None"
        )

    def test_project_id_zero(self):
        assert s3_handler._parse_project_id("projects/0/documents/file.pdf") == 0, (
            "project_id of zero should be parsed correctly"
        )


# handler() - end-to-end with moto


class TestHandler:
    """Full handler() execution: routing, quota check, delete branch"""

    #  helpers

    @staticmethod
    def _make_event(*keys: str) -> dict:
        """Build a minimal S3 ObjectCreated event with one record per key."""
        return {"Records": [{"s3": {"object": {"key": key}}} for key in keys]}

    #  basic routing

    def test_returns_200_always(self, s3_bucket):
        with patch.object(s3_handler, "S3", s3_bucket):
            result = s3_handler.handler(
                self._make_event("projects/10/documents/x.pdf"), None
            )
        assert result == {"statusCode": 200}, "handler should always return 200"

    def test_unknown_key_pattern_skipped(self, s3_bucket, caplog):
        with patch.object(s3_handler, "S3", s3_bucket):
            with caplog.at_level("WARNING", logger=""):
                result = s3_handler.handler(
                    self._make_event("unrecognised/path/file.pdf"), None
                )
        assert result == {"statusCode": 200}, "handler should always return 200"
        assert "Unrecognised key pattern" in caplog.text, (
            "handler should log a warning for unrecognised key patterns"
        )

    def test_empty_records_list(self, s3_bucket):
        with patch.object(s3_handler, "S3", s3_bucket):
            result = s3_handler.handler({"Records": []}, None)
        assert result == {"statusCode": 200}, "handler should always return 200"

    def test_missing_records_key(self, s3_bucket):
        with patch.object(s3_handler, "S3", s3_bucket):
            result = s3_handler.handler({}, None)
        assert result == {"statusCode": 200}, "handler should always return 200"

    #  below-limit: file is kept

    def test_under_limit_file_not_deleted(self, s3_bucket):
        key = "projects/20/documents/small.pdf"
        _put_object(s3_bucket, key, LIMIT - 1)  # 99 bytes < 100-byte limit

        with patch.object(s3_handler, "S3", s3_bucket):
            s3_handler.handler(self._make_event(key), None)

        # Object must still exist
        head = s3_bucket.head_object(Bucket=BUCKET, Key=key)
        assert head["ContentLength"] == LIMIT - 1, (
            "Object should not be deleted if total size is under the limit"
        )

    def test_exactly_at_limit_not_deleted(self, s3_bucket):
        """Boundary: total == LIMIT must NOT trigger deletion (> not >=)."""
        key = "projects/21/documents/boundary.pdf"
        _put_object(s3_bucket, key, LIMIT)  # exactly 100 bytes

        with patch.object(s3_handler, "S3", s3_bucket):
            s3_handler.handler(self._make_event(key), None)

        head = s3_bucket.head_object(Bucket=BUCKET, Key=key)
        assert head["ContentLength"] == LIMIT, (
            "Object should not be deleted if total size equals the limit"
        )

    #  over-limit: offending file is deleted

    def test_over_limit_offending_file_deleted(self, s3_bucket, caplog):
        key = "projects/30/documents/big.pdf"
        _put_object(s3_bucket, key, LIMIT + 1)

        with patch.object(s3_handler, "S3", s3_bucket):
            with caplog.at_level("WARNING"):
                s3_handler.handler(self._make_event(key), None)

        # Assert on the specific project to avoid cross-test log pollution
        assert "project_id=30 exceeded quota" in caplog.text, (
            "handler should log a warning when project exceeds quota"
        )
        assert "projects/30/documents/big.pdf" in caplog.text, (
            "handler should log the specific file that exceeded the quota"
        )

        with pytest.raises(Exception):
            s3_bucket.head_object(Bucket=BUCKET, Key=key)

    def test_over_limit_only_offending_file_deleted(self, s3_bucket):
        safe_key = "projects/31/documents/existing.pdf"
        offending_key = "projects/31/documents/new_big.pdf"
        _put_object(s3_bucket, safe_key, 60)
        _put_object(s3_bucket, offending_key, 60)  # total 120 > 100

        with patch.object(s3_handler, "S3", s3_bucket):
            s3_handler.handler(self._make_event(offending_key), None)

            # Assert inside the patch so s3_bucket client is still the active one
            with pytest.raises(Exception):
                s3_bucket.head_object(Bucket=BUCKET, Key=offending_key)

            head = s3_bucket.head_object(Bucket=BUCKET, Key=safe_key)
            assert head["ContentLength"] == 60, (
                "Existing file should not be deleted when a new file causes the project to exceed its quota"  # noqa: E501
            )

    #  error resilience

    def test_sum_error_logged_continues_to_next_record(self, s3_bucket, caplog):
        """
        If _sum_project_size raises, the handler logs the error and moves to
        the next record without crashing.
        """
        good_key = "projects/40/documents/good.pdf"
        _put_object(s3_bucket, good_key, 10)

        boom_client = MagicMock(wraps=s3_bucket)
        call_count = 0
        original_paginator = s3_bucket.get_paginator

        def _selective_paginator(operation):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Transient S3 error")
            return original_paginator(operation)

        boom_client.get_paginator.side_effect = _selective_paginator

        event = self._make_event(
            "projects/50/documents/boom.pdf",  # first → will fail
            good_key,  # second → must succeed
        )

        with patch.object(s3_handler, "S3", boom_client):
            with caplog.at_level("ERROR", logger=""):
                result = s3_handler.handler(event, None)

        assert result == {"statusCode": 200}, (
            " handler should continue processing after a _sum_project_size error"
        )
        assert "Failed to calculate storage" in caplog.text, (
            " handler should log an error when _sum_project_size raises an exception"
        )

    def test_delete_failure_logged_does_not_raise(self, s3_bucket, caplog):
        """If delete_object fails, the handler logs the error and still returns 200."""
        key = "projects/60/documents/huge.pdf"
        _put_object(s3_bucket, key, LIMIT + 1)

        broken_delete = MagicMock(wraps=s3_bucket)
        broken_delete.delete_object.side_effect = RuntimeError("Delete denied")

        with patch.object(s3_handler, "S3", broken_delete):
            with caplog.at_level("ERROR", logger=""):
                result = s3_handler.handler(self._make_event(key), None)

        assert result == {"statusCode": 200}, (
            " handler should return 200 even if file deletion fails"
        )
        assert "Failed to delete offending file" in caplog.text, (
            " handler should log an error when delete_object raises an exception"
        )

    #  multi-record event

    def test_multiple_records_processed_independently(self, s3_bucket):
        """Two records from different projects are processed independently."""
        key_a = "projects/70/documents/a.pdf"
        key_b = "projects/71/documents/b.pdf"
        _put_object(s3_bucket, key_a, 10)  # well under limit
        _put_object(s3_bucket, key_b, 10)  # well under limit

        with patch.object(s3_handler, "S3", s3_bucket):
            result = s3_handler.handler(self._make_event(key_a, key_b), None)

        assert result == {"statusCode": 200}, (
            " handler should return 200 for multiple records"
        )
        # Both files survive
        assert s3_bucket.head_object(Bucket=BUCKET, Key=key_a), (
            "File a.pdf should survive since its project is under the limit"
        )
        assert s3_bucket.head_object(Bucket=BUCKET, Key=key_b), (
            "File b.pdf should survive since its project is under the limit"
        )
