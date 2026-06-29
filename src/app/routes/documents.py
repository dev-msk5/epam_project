# CRUD /document/<id>, /project/<id>/documents
"""
- GET /project/<project_id>/documents       (Get all project documents)
- POST /project/<project_id>/documents      (Upload document(s))
- GET /document/<document_id>               (Download document)
- PUT /document/<document_id>               (Update document)
- DELETE /document/<document_id>            (Delete document)
"""

from typing import List

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.pydantic_schemas.document import DocumentDownloadOut, DocumentOut
from app.services.document import ALLOWED_EXT, DocumentService

router = APIRouter()


def _validate_file_types(files: list[UploadFile]) -> None:
    """Validate that all files have allowed extensions"""
    for f in files:
        name = (f.filename or "").rsplit(".", 1)
        ext = f".{name[-1].lower()}" if len(name) == 2 else ""
        if ext not in ALLOWED_EXT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"File '{f.filename}' has unsupported type. "
                f"Allowed: {sorted(ALLOWED_EXT)}",
            )


@router.get(
    "/project/{project_id}/documents",
    response_model=List[DocumentOut],
    status_code=status.HTTP_200_OK,
)
async def get_project_docs(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all documents for a specific project. User must have access to the project"""
    return await DocumentService.list_documents(
        session=session,
        project_id=project_id,
        user_id=current_user.id,
    )


@router.post(
    "/project/{project_id}/documents",
    response_model=List[DocumentOut],
    status_code=status.HTTP_201_CREATED,
)
async def post_project_docs(
    project_id: int,
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload one or more documents to a specific project. User must have access"""
    _validate_file_types(files)
    return await DocumentService.upload_documents(
        session=session, project_id=project_id, user_id=current_user.id, files=files
    )


@router.get(
    "/document/{document_id}",
    response_model=DocumentDownloadOut,
    status_code=status.HTTP_200_OK,
)
async def get_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get the download URL for a specific document. User must have access to the document"""
    return await DocumentService.get_document_download_url(
        session, document_id, current_user.id
    )


@router.put(
    "/document/{document_id}",
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
)
async def put_document(
    document_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a specific document. User must have access to the document"""
    _validate_file_types([file])
    return await DocumentService.update_document(
        session=session, document_id=document_id, user_id=current_user.id, file=file
    )


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific document. User must have access to the document"""
    await DocumentService.delete_document(session, document_id, current_user.id)
    # Bypasses response serialization to guarantee exactly a 0-byte payload
    return Response(status_code=status.HTTP_204_NO_CONTENT)
