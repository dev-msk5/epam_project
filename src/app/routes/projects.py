from fastapi import APIRouter

router = APIRouter()

"""
GET /project/<project_id>/info - Return project’s details, if user has access
PUT /project/<project_id>/info - Update projects details - name, description. Returns the updated project’s info
DELETE /project/<project_id>- Delete project, can only be performed by the projects’ owner. Deletes the corresponding  documents
GET /project/<project_id>/documents- Return all of the project's documents
POST /project/<project_id>/documents - Upload document/documents for a specific project
"""


@router.get("/project/{project_id}/info")
async def get_project_info(project_id: int):
    return {"message": f"Project info for project {project_id}"}


@router.put("/project/{project_id}/info")
async def put_project_info(project_id: int, name: str, description: str):
    return {"message": f"Project {project_id} updated with name: {name} and description: {description}"}


@router.delete("/project/{project_id}")
async def delete_project(project_id: int):
    # only by the projects owner
    return {"message": f"Project {project_id} deleted"}
