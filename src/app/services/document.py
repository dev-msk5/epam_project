from __future__ import annotations

import logging
import re
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.access import Access
from app.models.document import Document
from app.models.project import Project
from app.pydantic_schemas.document import DocumentDownloadOut, DocumentOut
from app.s3 import S3Service

log = logging.getLogger(__name__)
# Only allow PDF and DOCX to prevent arbitrary file uploads and reduce security surface
ALLOWED_EXT = {".pdf", ".docx"}


class DocumentService:
    @staticmethod
    def _safe_filename(name: str) -> str:
        """
        Sanitize and validate filenames to prevent path traversal, injection attacks,
        and ensure consistent storage structure in S3

        Security considerations:
        - Strips backslashes and takes only the final path component
        (prevents ../.. traversal)
        - Rejects empty/hidden files (starting with dot)
        - Allows only alphanumeric, dot, underscore, and hyphen in basename
        - Validates extension against ALLOWED_EXT whitelist (not blacklist)
        - Converts extension to lowercase for consistency

        Returns sanitized filename or raises HTTPException if invalid.
        """
        name = (name or "").strip().replace("\\", "/").split("/")[-1]
        if not name or name.startswith("."):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid filename")
        base, dot, ext = name.rpartition(".")
        ext = f".{ext.lower()}" if dot else ""
        base = re.sub(r"[^a-zA-Z0-9._-]", "_", base).strip("._-")
        if not base or ext not in ALLOWED_EXT:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Allowed extensions: {sorted(ALLOWED_EXT)}",
            )
        return f"{base}{ext}"

    @staticmethod
    async def _lock_project(session: AsyncSession, project_id: int) -> Project:
        """
        Fetch and lock a project row for exclusive access during the upload transaction

        Using FOR UPDATE ensures:
        - Only one concurrent upload can proceed for a given project
        - Quota checks use consistent, locked data (prevents race conditions)
        - Multiple concurrent requests queue, serialize naturally

        This prevents the "read-compute-write" race where 2 requests both see available
        quota, both upload, and together exceed the limit
        """
        project = (
            await session.execute(
                select(Project).where(Project.id == project_id).with_for_update()
                # Fetch the project with this ID,
                # lock it so no other transaction can modify it while occupied
                # One Project row is expected, if more than one, it will raise an error
                # (should not happen with proper DB constraints)
            )
        ).scalar_one_or_none()
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        return project

    @staticmethod
    async def _get_role(session: AsyncSession, project_id: int, user_id: int) -> str:
        """Returns the role of the user in the project (owner or participant)
        or raises HTTPException if no access"""
        # check if owner first
        project = (
            await session.execute(select(Project).where(Project.id == project_id))
        ).scalar_one_or_none()

        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

        if project.owner_id == user_id:
            return "owner"

        # check Access table for participants
        role = (
            await session.execute(
                select(Access.role).where(
                    Access.project_id == project_id, Access.user_id == user_id
                )
            )
        ).scalar_one_or_none()

        if not role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No access")

        return role

    @staticmethod
    async def _project_usage(session: AsyncSession, project_id: int) -> int:
        """
        Calculate total storage used by all documents in a project (including pending).

        Uses SQL SUM aggregation to compute total size in bytes
        Returns 0 if no documents exist (via COALESCE)
        Called during quota validation before upload
        """
        return int(
            (
                await session.execute(
                    select(func.coalesce(func.sum(Document.size), 0)).where(
                        # Compute the total size of all documents in this project,
                        # if no documents, return 0
                        Document.project_id == project_id
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def _file_size(file: UploadFile) -> int:
        """
        Get file size by seeking to EOF without reading entire content into memory.

        Restores original file position after measurement to avoid side effects.
        This method is lightweight and called before quota checks to early-reject
        oversized uploads.
        """
        pos = file.file.tell()  # current position
        # seek to end of file, relative to the EOF (2) to get the size
        file.file.seek(0, 2)
        # get the size by telling the position at the end, the diff is the size
        size = file.file.tell()
        file.file.seek(pos)  # restore original position
        return size

    @staticmethod
    async def _cleanup_s3(keys: list[str]) -> None:
        """
        Delete files from S3 with fault tolerance.

        Logs and continues on individual failures rather than raising.
        This ensures one failed deletion doesn't block cleanup of remaining files.
        Called during transaction rollback (best-effort cleanup).
        """
        for key in keys:
            try:
                await S3Service.delete_file(key)
            except Exception:
                log.exception("Failed to delete S3 object: %s", key)

    # Public methods for document operations (upload, list, update, delete, download)

    @classmethod
    async def upload_documents(
        cls,
        session: AsyncSession,
        project_id: int,
        user_id: int,
        files: list[UploadFile],
    ) -> list[DocumentOut]:
        """Upload multiple documents to a project
        with quota validation and S3 storage"""
        if not files:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No files provided")

        project = await cls._lock_project(session, project_id)  # noqa: F841
        await cls._get_role(session, project_id, user_id)

        items, total = [], 0
        for f in files:
            name = cls._safe_filename(f.filename or "")
            size = await cls._file_size(f)
            total += size
            items.append((f, name, size))

        used = await cls._project_usage(session, project_id)
        if used + total > settings.PROJECT_STORAGE_LIMIT_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Quota exceeded"
            )

        upload_id = uuid.uuid4().hex
        docs = []
        for _, name, size in items:
            doc = Document(
                project_id=project_id,
                owner_id=user_id,
                name=name,
                size=size,
                is_pending=True,
                url="",
            )
            session.add(doc)
            docs.append(doc)

        await session.flush()
        for doc in docs:
            doc.url = f"projects/{project_id}/documents/{doc.id}_{upload_id}_{doc.name}"

        uploaded = []
        try:
            for (file, _, _), doc in zip(items, docs, strict=True):
                file.file.seek(0)
                await S3Service.upload_file(
                    file.file,
                    doc.url,
                    file.content_type or "application/octet-stream",
                )
                uploaded.append(doc.url)

            for doc in docs:
                doc.is_pending = False

            await session.commit()
            for doc in docs:
                await session.refresh(doc)
            return [DocumentOut.model_validate(d) for d in docs]

        except Exception:
            # Clean up S3 files that were uploaded
            await cls._cleanup_s3(uploaded)

            # ✅ Rollback DB changes — this discards all pending inserts
            await session.rollback()

            # ❌ DO NOT try to delete docs here — rollback already discarded them
            # The session is now clean; no manual delete needed

            raise

    @classmethod
    async def list_documents(
        cls,
        session: AsyncSession,
        project_id: int,
        user_id: int,
    ) -> list[DocumentOut]:
        """
        List all completed documents in a project

        Filters:
        - Only documents belonging to this project
        - Only non-pending (is_pending=False) — in-progress uploads excluded

        Access control: verifies user is a project member (any role).
        """
        await cls._get_role(session, project_id, user_id)
        docs = (
            (
                await session.execute(
                    select(Document).where(
                        Document.project_id == project_id,
                        Document.is_pending.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        return [DocumentOut.model_validate(d) for d in docs]

    @classmethod
    async def update_document(
        cls,
        session: AsyncSession,
        document_id: int,
        user_id: int,
        file: UploadFile,
    ) -> DocumentOut:
        """
        Replace a document's content with quota re-validation

        Locking & validation:
        - Lock document row (with_for_update) to serialize concurrent updates
        - Verify user is a project member (participant or owner)
        - Any project member can update (not just original uploader)

        Quota: re-calculated as (used - old_size + new_size) to account for replacement

        S3 operations:
        - Upload new file to new S3 key (versioning via UUID)
        - seek(0) before upload ensures full content
        - On success: delete old S3 file (cleanup after DB commit)
        - On failure: delete new S3 file only (old file preserved)
        """
        doc = (
            await session.execute(
                select(Document).where(Document.id == document_id).with_for_update()
            )
        ).scalar_one_or_none()
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        # any project member (owner or participant) may update
        # no longer tied to who originally uploaded the file
        await cls._get_role(session, doc.project_id, user_id)

        name = cls._safe_filename(file.filename or "")
        size = await cls._file_size(file)
        used = await cls._project_usage(session, doc.project_id)
        if used - int(doc.size or 0) + size > settings.PROJECT_STORAGE_LIMIT_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Quota exceeded"
            )

        old_key = doc.url
        new_key = (
            f"projects/{doc.project_id}/documents/{doc.id}_{uuid.uuid4().hex}_{name}"
        )
        try:
            # seek to the beginning before uploading so S3 receives
            # the full file content and not 0 bytes
            file.file.seek(0)
            await S3Service.upload_file(
                file.file,
                new_key,
                file.content_type or "application/octet-stream",
            )
            doc.name, doc.url, doc.size, doc.is_pending = name, new_key, size, False
            await session.commit()
            await session.refresh(doc)
        except Exception:
            await cls._cleanup_s3([new_key])
            raise

        if old_key and old_key != new_key:
            await cls._cleanup_s3([old_key])
        return DocumentOut.model_validate(doc)

    @classmethod
    async def delete_document(
        cls,
        session: AsyncSession,
        document_id: int,
        user_id: int,
    ) -> None:
        """
        Delete a document and its S3 file, only project owners allowed

        Permission model:
        - Owner: can delete any document
        - Participant: cannot delete (can only view/update)

        Access control is role-based (owner/participant), not ownership-based
        This ensures team leads can clean up stale documents,
        regardless of who uploaded them

        S3 cleanup is asynchronous (after DB commit) to avoid transaction latency
        """
        doc = (
            await session.execute(
                select(Document).where(Document.id == document_id).with_for_update()
            )
        ).scalar_one_or_none()
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        # only the project OWNER may delete, role-based, not document-uploader-based
        # This is the rule the spec requires:
        # "participant: can modify, cannot delete"
        role = await cls._get_role(session, doc.project_id, user_id)
        if role != "owner":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Only project owner can delete"
            )

        key = doc.url
        await session.delete(doc)
        await session.commit()
        if key:
            await cls._cleanup_s3([key])

    @classmethod
    async def get_document_download_url(
        cls,
        session: AsyncSession,
        document_id: int,
        user_id: int,
    ) -> DocumentDownloadOut:
        """
        Generate a time-limited S3 download URL for a document.

        Validation:
        - Document exists
        - User is a project member
        - Document is not pending (upload completed)

        Returns: Pydantic model with document metadata + signed S3 download URL.
        The download URL has expiration enforced by S3 (prevents long-term sharing).
        """
        doc = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        await cls._get_role(session, doc.project_id, user_id)
        if doc.is_pending:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Document is still being processed"
            )
        return DocumentDownloadOut(
            **DocumentOut.model_validate(doc).model_dump(),
            download_url=S3Service.generate_download_url(doc.url),
        )
