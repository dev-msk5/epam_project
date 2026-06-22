"""
 - POST /projects                      (Create project)
  - GET /projects                       (Get all accessible projects)
  - GET /project/<project_id>/info      (Get project details)
  - PUT /project/<project_id>/info      (Update project details)
  - DELETE /project/<project_id>        (Delete project)
  - POST /project/<project_id>/invite?user=<login>  (Grant access to user)
  
  - GET /project/<project_id>/share?with=<email>   (Send share link via email - Optional Phase 1)
"""
from fastapi import APIRouter
router = APIRouter()


@router.get("/projects")
async def get_projects():
    return {"message": "List of projects"}


@router.post("/project/{project_id}/invite?user={login}")
async def invite_user(project_id: int, login: str):
    # if project_owner != current_user:
    #    return {"error": "Only project owner can invite users"}
    return {"message": f"User {login} invited to project {project_id}"}


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
