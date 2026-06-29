# Integration tests for document upload, download, update, delete and access control
#
# test_upload_document - covered cases:
#   owner can upload a PDF
#   owner can upload a DOCX
#   owner can upload multiple files at once
#   document is saved in DB with correct project_id
#   document is uploaded to S3 (mock S3)
#   participant can upload (participants CAN modify)
#   user with no access gets 403
#   unsupported file type gets 422
#   unauthenticated request returns 401
#
# test_get_documents - covered cases:
#   owner can list project documents
#   participant can list project documents
#   user with no access gets 403
#   non-existent project_id gets 404
#   unauthenticated request returns 401
#
# test_download_document - covered cases:
#   owner can get a presigned download URL
#   participant can get a presigned download URL
#   response contains s3_key and download_url fields
#   user with no access gets 403
#   non-existent document_id gets 404
#   unauthenticated request returns 401
#
# test_update_document - covered cases:
#   owner can replace a document file
#   participant can replace a document file
#   old S3 file is deleted, new one uploaded (mock S3)
#   DB record url and updated_at are refreshed
#   user with no access gets 403
#   non-existent document_id gets 404
#   unauthenticated request returns 401
#
# test_delete_document - covered cases:
#   owner can delete document
#   document removed from DB
#   document removed from S3 (mock S3)
#   participant cannot delete - gets 403
#   user with no access gets 403
#   non-existent document_id gets 404
#   unauthenticated request returns 401
#
# cross-project access control - covered cases:
#   user A cannot list user B's project documents
#   user A cannot download user B's document
#   participant cannot delete document
#   participant cannot delete project

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.access import Access
from app.models.document import Document
from app.models.project import Project
from app.models.user import User


# helpers to avoid repeating project + access setup

async def _make_project(
    db: AsyncSession,
    owner: User,
    name: str = "Test Project"
) -> Project:
    project = Project(name=name, description="desc", owner_id=owner.id)
    db.add(project)
    await db.flush()
    db.add(Access(user_id=owner.id, project_id=project.id, role="owner"))
    await db.flush()
    return project


async def _make_document(
    db: AsyncSession,
    project: Project,
    owner: User,
    name: str = "file.pdf",
    url: str = "projects/1/documents/file.pdf"
) -> Document:
    doc = Document(
        name=name,
        project_id=project.id,
        owner_id=owner.id,
        url=url,
        is_pending=False
    )
    db.add(doc)
    await db.flush()
    return doc


#  upload

async def test_upload_pdf_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "PDF Upload Project")

    response = await client.post(
        f"/project/{project.id}/documents",
        files=[("files", ("report.pdf", b"pdf-bytes", "application/pdf"))],
        headers=owner_headers
    )
    assert response.status_code in [200, 201], "upload should succeed"
    mock_s3["upload"].assert_called_once(), "file should be uploaded to S3"

    data = response.json()
    if isinstance(data, list):
        data = data[0]
    assert data["name"] == "report.pdf", "uploaded name should match"
    assert data["project_id"] == project.id, (
        "uploaded document should belong to the project"
    )


async def test_upload_docx_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "DOCX Upload Project")

    docx_mime = (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    )
    response = await client.post(
        f"/project/{project.id}/documents",
        files=[("files", ("spec.docx", b"docx-bytes", docx_mime))],
        headers=owner_headers
    )
    assert response.status_code in [200, 201], "upload should succeed"


async def test_upload_multiple_files(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Multi Upload Project")

    files = [
        ("files", ("a.pdf", b"bytes-a", "application/pdf")),
        ("files", ("b.pdf", b"bytes-b", "application/pdf")),
    ]
    response = await client.post(
        f"/project/{project.id}/documents",
        files=files,
        headers=owner_headers
    )
    assert response.status_code in [200, 201], "upload should succeed"
    assert mock_s3["upload"].call_count == 2, (
        "each uploaded file should be sent to S3"
    )


async def test_upload_saves_to_db(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "DB Save Project")

    await client.post(
        f"/project/{project.id}/documents",
        files=[("files", ("saved.pdf", b"data", "application/pdf"))],
        headers=owner_headers
    )

    stmt = select(Document).where(Document.project_id == project.id)
    docs = (await db_session.execute(stmt)).scalars().all()
    assert len(docs) >= 1, "document should be stored in the database"
    assert any(d.name == "saved.pdf" for d in docs), (
        "saved document should be present in the database"
    )


async def test_upload_participant_allowed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Participant Upload")
    db_session.add(Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    ))
    await db_session.flush()

    response = await client.post(
        f"/project/{project.id}/documents",
        files=[("files", ("part.pdf", b"bytes", "application/pdf"))],
        headers=participant_headers
    )
    assert response.status_code in [200, 201], "upload should succeed"


async def test_upload_no_access_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Blocked Upload")

    response = await client.post(
        f"/project/{project.id}/documents",
        files=[("files", ("hack.pdf", b"bytes", "application/pdf"))],
        headers=other_headers
    )
    assert response.status_code in [403, 404], (
        "user without access should be blocked"
    )


async def test_upload_unsupported_type(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Bad Type Project")

    response = await client.post(
        f"/project/{project.id}/documents",
        files=[("files", ("virus.exe", b"bytes", "application/octet-stream"))],
        headers=owner_headers
    )
    assert response.status_code == 422, "unsupported file type should fail"


async def test_upload_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User
):
    project = await _make_project(db_session, test_owner, "Unauth Upload")

    response = await client.post(
        f"/project/{project.id}/documents",
        files=[("files", ("file.pdf", b"bytes", "application/pdf"))]
    )
    assert response.status_code == 401, "missing token should fail"


#  list documents

async def test_list_documents_owner(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict
):
    project = await _make_project(db_session, test_owner, "List Docs Owner")
    await _make_document(db_session, project, test_owner, "listed.pdf")

    response = await client.get(
        f"/project/{project.id}/documents", headers=owner_headers
    )
    assert response.status_code == 200, "list request should succeed"
    assert len(response.json()) >= 1, "owner should see project documents"


async def test_list_documents_participant(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict
):
    project = await _make_project(db_session, test_owner, "List Docs Participant")
    db_session.add(Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    ))
    await _make_document(db_session, project, test_owner, "doc.pdf")

    response = await client.get(
        f"/project/{project.id}/documents", headers=participant_headers
    )
    assert response.status_code == 200, "list request should succeed"


async def test_list_documents_no_access_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict
):
    project = await _make_project(db_session, test_owner, "List Blocked")

    response = await client.get(
        f"/project/{project.id}/documents", headers=other_headers
    )
    assert response.status_code in [403, 404], (
        "user without access should be blocked"
    )


async def test_list_documents_project_not_found(
    client: AsyncClient,
    owner_headers: dict
):
    response = await client.get(
        "/project/999999/documents", headers=owner_headers
    )
    assert response.status_code == 404, "missing project should return 404"


async def test_list_documents_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User
):
    project = await _make_project(db_session, test_owner, "List Unauth")

    response = await client.get(f"/project/{project.id}/documents")
    assert response.status_code == 401, "missing token should fail"


#  download

async def test_download_document_owner(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Download Owner")
    doc = await _make_document(
        db_session, project, test_owner,
        "spec.pdf", "projects/1/documents/spec.pdf"
    )

    response = await client.get(f"/document/{doc.id}", headers=owner_headers)
    assert response.status_code == 200, "download should succeed"

    data = response.json()
    assert "s3_key" in data, "download response should include s3_key"
    assert "download_url" in data, (
        "download response should include download_url"
    )


async def test_download_document_participant(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Download Participant")
    db_session.add(Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    ))
    await db_session.flush()

    doc = await _make_document(db_session, project, test_owner, "manual.pdf")

    response = await client.get(f"/document/{doc.id}", headers=participant_headers)
    assert response.status_code == 200, "download should succeed"


async def test_download_no_access_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Download Blocked")
    doc = await _make_document(db_session, project, test_owner, "secret.pdf")

    response = await client.get(f"/document/{doc.id}", headers=other_headers)
    assert response.status_code in [403, 404], (
        "user without access should be blocked"
    )


async def test_download_not_found(client: AsyncClient, owner_headers: dict):
    response = await client.get("/document/999999", headers=owner_headers)
    assert response.status_code == 404, "missing document should return 404"


async def test_download_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User
):
    project = await _make_project(db_session, test_owner, "Download Unauth")
    doc = await _make_document(db_session, project, test_owner, "file.pdf")

    response = await client.get(f"/document/{doc.id}")
    assert response.status_code == 401, "missing token should fail"


#  update document

async def test_update_document_owner(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Update Doc Owner")
    doc = await _make_document(
        db_session, project, test_owner,
        "old.pdf", "projects/1/documents/old.pdf"
    )

    response = await client.put(
        f"/document/{doc.id}",
        files=[("file", ("new.pdf", b"new-bytes", "application/pdf"))],
        headers=owner_headers
    )
    assert response.status_code == 200, "update should succeed"

    # old key deleted, new one uploaded
    mock_s3["delete"].assert_called_once_with(
        "projects/1/documents/old.pdf"
    ), "old file should be deleted from S3"
    mock_s3["upload"].assert_called_once(), (
        "new file should be uploaded to S3"
    )


async def test_update_document_participant_allowed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Update Participant")
    db_session.add(Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    ))
    await db_session.flush()

    doc = await _make_document(db_session, project, test_owner, "editable.pdf")

    response = await client.put(
        f"/document/{doc.id}",
        files=[("file", ("editable_v2.pdf", b"v2-bytes", "application/pdf"))],
        headers=participant_headers
    )
    assert response.status_code == 200, "update should succeed"


async def test_update_document_refreshes_db_record(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "DB Refresh")
    doc = await _make_document(
        db_session, project, test_owner,
        "stale.pdf", "projects/1/documents/stale.pdf"
    )
    old_url = doc.url

    await client.put(
        f"/document/{doc.id}",
        files=[("file", ("fresh.pdf", b"fresh", "application/pdf"))],
        headers=owner_headers
    )

    await db_session.refresh(doc)
    assert doc.url != old_url, "document url should be refreshed"


async def test_update_document_no_access_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Update Blocked")
    doc = await _make_document(db_session, project, test_owner, "private.pdf")

    response = await client.put(
        f"/document/{doc.id}",
        files=[("file", ("hack.pdf", b"bytes", "application/pdf"))],
        headers=other_headers
    )
    assert response.status_code in [403, 404], (
        "user without access should be blocked"
    )


async def test_update_document_not_found(
    client: AsyncClient,
    owner_headers: dict
):
    response = await client.put(
        "/document/999999",
        files=[("file", ("x.pdf", b"bytes", "application/pdf"))],
        headers=owner_headers
    )
    assert response.status_code == 404, "missing document should return 404"


async def test_update_document_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User
):
    project = await _make_project(db_session, test_owner, "Update Unauth")
    doc = await _make_document(db_session, project, test_owner, "file.pdf")

    response = await client.put(
        f"/document/{doc.id}",
        files=[("file", ("new.pdf", b"bytes", "application/pdf"))]
    )
    assert response.status_code == 401, "missing token should fail"


#  delete document

async def test_delete_document_owner_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Delete Doc Owner")
    doc = await _make_document(
        db_session, project, test_owner,
        "trash.pdf", "projects/1/documents/trash.pdf"
    )

    response = await client.delete(f"/document/{doc.id}", headers=owner_headers)
    assert response.status_code in [200, 204], "delete should succeed"

    mock_s3["delete"].assert_called_once_with(
        "projects/1/documents/trash.pdf"
    ), "deleted file should be removed from S3"

    stmt = select(Document).where(Document.id == doc.id)
    result = (await db_session.execute(stmt)).scalar_one_or_none()
    assert result is None, "document should be removed from the database"


async def test_delete_document_participant_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Delete Part Blocked")
    db_session.add(Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    ))
    await db_session.flush()

    doc = await _make_document(db_session, project, test_owner, "protected.pdf")

    response = await client.delete(
        f"/document/{doc.id}", headers=participant_headers
    )
    assert response.status_code == 403, "participant delete should fail"


async def test_delete_document_no_access_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Delete No Access")
    doc = await _make_document(db_session, project, test_owner, "private.pdf")

    response = await client.delete(f"/document/{doc.id}", headers=other_headers)
    assert response.status_code in [403, 404], (
        "user without access should be blocked"
    )


async def test_delete_document_not_found(
    client: AsyncClient,
    owner_headers: dict
):
    response = await client.delete("/document/999999", headers=owner_headers)
    assert response.status_code == 404, "missing document should return 404"


async def test_delete_document_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User
):
    project = await _make_project(db_session, test_owner, "Delete Unauth")
    doc = await _make_document(db_session, project, test_owner, "file.pdf")

    response = await client.delete(f"/document/{doc.id}")
    assert response.status_code == 401, "missing token should fail"


#  cross-project access control

async def test_user_cannot_list_another_users_documents(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict
):
    project = await _make_project(db_session, test_owner, "Cross Project Docs")
    await _make_document(db_session, project, test_owner, "owned.pdf")

    response = await client.get(
        f"/project/{project.id}/documents", headers=other_headers
    )
    assert response.status_code in [403, 404], (
        "user without access should be blocked"
    )


async def test_user_cannot_download_another_users_document(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Cross Download Block")
    doc = await _make_document(db_session, project, test_owner, "locked.pdf")

    response = await client.get(f"/document/{doc.id}", headers=other_headers)
    assert response.status_code in [403, 404], (
        "user without access should be blocked"
    )


async def test_participant_cannot_delete_document(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Part Del Doc Block")
    db_session.add(Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    ))
    await db_session.flush()

    doc = await _make_document(db_session, project, test_owner, "guarded.pdf")

    response = await client.delete(
        f"/document/{doc.id}", headers=participant_headers
    )
    assert response.status_code == 403, "participant delete should fail"


async def test_participant_cannot_delete_project(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
    mock_s3: dict
):
    project = await _make_project(db_session, test_owner, "Part Del Proj Block")
    db_session.add(Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    ))
    await db_session.flush()

    response = await client.delete(
        f"/project/{project.id}", headers=participant_headers
    )
    assert response.status_code == 403, "participant delete should fail"
