# upload, download, delete, access control

# test_upload_document()
#  owner can upload a PDF
#  owner can upload a DOCX
#  owner can upload multiple files at once
#  document is saved in DB with correct project_id
#  document is uploaded to S3 (mock S3)
#  participant can upload (participants CAN modify)
#  user with no access gets 403
#  unsupported file type (e.g. .exe) gets 422
#  unauthenticated request returns 401

# test_get_documents()
#  owne can list project documents
#  participant can list project documents
#  user with no access gets 403
#  non-existent project_id gets 404
#  unauthenticated request returns 401

# test_download_document()
#  owner can download document
#  participant can download document
#  response is the actual file bytes (not JSON)
#  user with no access gets 403
#  non-existent document_id gets 404
#  unauthenticated request returns 401

# test_update_document()
#  owner can replace document file
#  participant can replace document file
#  old S3 file is deleted, new one uploaded (mock S3)
#  DB record is updated (url, updated_at)
#  user with no access gets 403
#  non-existent document_id gets 404
#  unauthenticated request returns 401

# test_delete_document()
#  owner can delete document
#  document removed from DB
#  document removed from S3 (mock S3)
#  participant CANNOT delete document — gets 403
#  user with no access gets 403
#  non-existent document_id gets 404
#  unauthenticated request returns 401

# access_control
#  user A cannot see user B's projects
#  user A cannot update user B's project
#  user A cannot delete user B's project
#  user A cannot download user B's documents
#  participant cannot delete project
#  participant cannot delete document
#  participant cannot invite other users
#  participant CAN read project info
#  participant CAN update project info
#  participant CAN upload documents
#  participant CAN download documents
# tests/test_documents.py
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User
from app.models.project import Project
from app.models.document import Document


async def test_upload_document_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    """Verify uploading a document yields a proper DocumentOut shape (maps url to s3_key)"""
    project = Project(name="Docs project",
                      description="Details", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    # Send document payload using the plural 'files' key to match FastAPI's multi-file endpoint parameter
    file_payload = [
        ("files", ("requirements.docx", b"document-binary-content-data",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
    ]

    response = await client.post(
        f"/project/{project.id}/documents",
        files=file_payload,
        headers=owner_headers
    )
    assert response.status_code in [
        200, 201], "Response should be 200 or 201 for successful document upload"

    # Ensure S3 helper upload was called
    mock_s3["upload"].assert_called_once()

    # Validate DocumentOut payload formatting and validation alias maps db 'url' -> 's3_key'
    resp_data = response.json()

    # If your endpoint returns a list of uploaded files, get the first one
    if isinstance(resp_data, list):
        resp_data = resp_data[0]

    assert "s3_key" in resp_data, "Response should contain 's3_key' field"
    assert "download_url" in resp_data, "Response should contain 'download_url' field"
    assert resp_data["s3_key"] == "projects/1/documents/mock_doc.pdf", "s3_key should match the mocked S3 upload return value"
    assert resp_data["name"] == "requirements.docx", "Document name should match the uploaded file"
    assert resp_data["project_id"] == project.id, "Document project_id should match the project"


async def test_get_presigned_download_url_authorized(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    """Verify getting a download link yields correct DocumentDownloadOut structure"""
    project = Project(name="Secure Project",
                      description="Desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    document = Document(
        name="specification.pdf",
        project_id=project.id,
        owner_id=test_owner.id,
        url="projects/1/documents/spec.pdf",
        is_pending=False
    )
    db_session.add(document)
    await db_session.flush()

    response = await client.get(f"/document/{document.id}", headers=owner_headers)
    assert response.status_code == 200, "Download request should succeed with 200 for authorized user"

    # Verify DocumentDownloadOut parameters
    data = response.json()
    assert data["s3_key"] == "projects/1/documents/spec.pdf", "s3_key should match the expected value"
    assert data["download_url"] == "https://mocked-s3-presigned-url.com/download", "download_url should match the expected value"

    mock_s3["url"].assert_called_once_with("projects/1/documents/spec.pdf")


async def test_delete_document_cleans_s3(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    """Verify that deleting a document triggers its S3 object cleanup synchronously and removes the DB record"""
    project = Project(name="Clean project",
                      description="Details", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    document = Document(
        name="trash.docx",
        project_id=project.id,
        owner_id=test_owner.id,
        url="projects/1/documents/trash.docx",
        is_pending=False
    )
    db_session.add(document)
    await db_session.flush()

    response = await client.delete(f"/document/{document.id}", headers=owner_headers)
    assert response.status_code in [
        200, 204], "Document deletion should succeed with 200 or 204"

    # Assert that delete was called on S3 helper with key parameter
    mock_s3["delete"].assert_called_once_with(
        "projects/1/documents/trash.docx")

    # Ensure database record is deleted
    stmt = select(Document).where(Document.id == document.id)
    doc_in_db = (await db_session.execute(stmt)).scalar_one_or_none()
    assert doc_in_db is None, "Document should be removed from the database after deletion"


async def test_cascading_project_deletion_cleans_s3(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict
):
    """Verify deleting a project cascade-deletes related documents and cleans up their S3 objects"""
    project = Project(name="Project To Delete",
                      description="Desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    doc1 = Document(
        name="file1.pdf", project_id=project.id, owner_id=test_owner.id,
        url="projects/1/documents/file1.pdf", is_pending=False
    )
    doc2 = Document(
        name="file2.pdf", project_id=project.id, owner_id=test_owner.id,
        url="projects/1/documents/file2.pdf", is_pending=False
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    # Delete the project (Owner action)
    response = await client.delete(f"/project/{project.id}", headers=owner_headers)
    assert response.status_code in [
        200, 204], "Project deletion should succeed with 200 or 204"

    # Verify that S3 delete_file was triggered for both files
    assert mock_s3["delete"].call_count == 2
    mock_s3["delete"].assert_any_call("projects/1/documents/file1.pdf")
    mock_s3["delete"].assert_any_call(
        "projects/1/documents/file2.pdf"), "S3 delete_file should be called for each document associated with the deleted project"
