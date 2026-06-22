# CRUD /document/<id>, /project/<id>/documents
#   - GET /project/<project_id>/documents       (Get all project documents)
#   - POST /project/<project_id>/documents      (Upload document(s))
#   - GET /document/<document_id>               (Download document)
#   - PUT /document/<document_id>               (Update document)
#   - DELETE /document/<document_id>            (Delete document)

from fastapi import APIRouter

router = APIRouter()


@router.get("/project/{project_id}/documents")
async def get_project_docs(project_id: int):
    # TODO better return
    return {"message": f"Documents for project {project_id}"}


@router.post("/project/{project_id}/documents")
async def post_project_docs(project_id: int):
    return {"message": f"Documents uploaded for project {project_id}"}


@router.get("/document/{document_id}")
async def get_document(document_id: int):
    # only if user has access to the corresponding project
    return {"message": f"Document {document_id} downloaded"}


@router.put("/document/{document_id}")
async def put_document(document_id: int):
    return {"message": f"Document {document_id} updated"}


@router.delete("/document/{document_id}")
async def delete_document(document_id: int):
    return {"message": f"Document {document_id} deleted"}
