# CRUD /document/<id>, /project/<id>/documents
#   - GET /project/<project_id>/documents       (Get all project documents)
#   - POST /project/<project_id>/documents      (Upload document(s))
#   - GET /document/<document_id>               (Download document)
#   - PUT /document/<document_id>               (Update document)
#   - DELETE /document/<document_id>            (Delete document)

from typing import List
from fastapi import UploadFile, File
from fastapi import APIRouter, Depends, HTTPException

from app.db.session import get_session
from app.models.document import Document

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.pydantic_schemas.document import DocumentOut

router = APIRouter()


# OK
@router.get("/project/{project_id}/documents", response_model=list[DocumentOut], status_code=200)
async def get_project_docs(project_id: int, session: AsyncSession = Depends(get_session)):
    # TODO check if user has access to the project
    docs = await session.execute(select(Document).where(Document.project_id == project_id))
    return docs.scalars().all()


# Created
@router.post("/project/{project_id}/documents", status_code=201, response_model=DocumentOut)
async def post_project_docs(
    project_id: int,
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    # current_user: User = Depends(get_current_user)
):
    # TODO check if user has access to the project
    # TODO save files to storage and create Document entries in the database
    return {"message": f"{len(files)} document(s) uploaded to project {project_id}"}


@router.get("/document/{document_id}", response_model=DocumentOut, status_code=200)
async def get_document(document_id: int):
    # only if user has access to the corresponding project
    return {"message": f"Document {document_id} downloaded"}


@router.put("/document/{document_id}", status_code=200, response_model=DocumentOut)
async def put_document(document_id: int):
    return {"message": f"Document {document_id} updated"}


# No Content
@router.delete("/document/{document_id}", status_code=204, response_model=None)
async def delete_document(document_id: int):
    return {"message": f"Document {document_id} deleted"}
