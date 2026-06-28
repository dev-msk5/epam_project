# AWS S3 helper (upload, download, delete, presigned URLs)
"""S3 keys use projects/{project_id}/documents/{document_id}_{filename}.

Lambda triggers on S3 events, so the document_id keeps uploads traceable and
avoids filename collisions.
"""

# boto3 is sync
# - upload_file()     Lambda triggers when this happens
# - delete_file()     needed for document/project deletion
# - download_file()  needed for document download

import io
import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from anyio.to_thread import run_sync

from app.config import settings

# Initialize the synchronous boto3 client; it is thread-safe for parallel use
s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


class S3Service:
    @staticmethod
    def _sync_upload_fileobj(file_obj, key: str, content_type: str) -> None:
        """
        Synchronous helper run in a separate worker thread
        Reads directly from the temporary file descriptor to keep memory consumption low
        """
        try:
            file_obj.seek(0)
            s3_client.upload_fileobj(
                file_obj,
                settings.S3_BUCKET_NAME,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"S3 Upload failed: {str(e)}",
            )

    @staticmethod
    def _sync_delete_file(key: str) -> None:
        """Synchronous helper run in a separate worker thread"""
        try:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete S3 file: {str(e)}",
            )

    # Public methods for async usage

    @classmethod
    async def upload_file(cls, file_obj, key: str, content_type: str) -> str:
        """
            Asynchronously upload a file-like stream to S3
            Streams from disk/buffer, preventing RAM bloat
        """
        await run_sync(cls._sync_upload_fileobj, file_obj, key, content_type)
        return key

    @staticmethod
    def generate_download_url(key: str, expiration: int = 900) -> str:
        """
        Generate a secure presigned download link synchronously

        The link expires after `expiration` seconds and avoids async overhead
        for this quick boto3 call.
        """
        try:
            return s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
                ExpiresIn=expiration,
            )
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate S3 URL: {str(e)}",
            )

    @classmethod
    async def delete_file(cls, key: str) -> None:
        """Asynchronously delete a file from the S3 bucket"""
        await run_sync(cls._sync_delete_file, key)  # worker thread
