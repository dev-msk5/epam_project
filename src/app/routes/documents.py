# CRUD /document/<id>, /project/<id>/documents
#   - GET /project/<project_id>/documents       (Get all project documents)
#   - POST /project/<project_id>/documents      (Upload document(s))
#   - GET /document/<document_id>               (Download document)
#   - PUT /document/<document_id>               (Update document)
#   - DELETE /document/<document_id>            (Delete document)

from fastapi import APIRouter, Depends

from app.db.session import get_session
from app.pydantic_schemas.document import Document

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()


# OK
@router.get("/project/{project_id}/documents", response_model=list[Document], response_code=200)
async def get_project_docs(project_id: int, session: AsyncSession = Depends(get_session)):
    # TODO check if user has access to the project
    docs = await session.execute(select(Document).where(Document.project_id == project_id))
    return docs.scalars().all()


@router.post("/project/{project_id}/documents", response_code=201)  # Created
async def post_project_docs(project_id: int):
    return {"message": f"Documents uploaded for project {project_id}"}


@router.get("/document/{document_id}", response_model=Document, response_code=200)
async def get_document(document_id: int):
    # only if user has access to the corresponding project
    return {"message": f"Document {document_id} downloaded"}


@router.put("/document/{document_id}", response_code=200)
async def put_document(document_id: int):
    return {"message": f"Document {document_id} updated"}


@router.delete("/document/{document_id}", response_code=204)  # No Content
async def delete_document(document_id: int):
    return {"message": f"Document {document_id} deleted"}
