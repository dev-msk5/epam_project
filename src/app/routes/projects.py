"""
 - POST /projects                      (Create project)
  - GET /projects                       (Get all accessible projects)
  - GET /project/<project_id>/info      (Get project details)
  - PUT /project/<project_id>/info      (Update project details)
  - DELETE /project/<project_id>        (Delete project)
  - POST /project/<project_id>/invite?user=<login>  (Grant access to user)
  
  - GET /project/<project_id>/share?with=<email>   (Send share link via email - Optional Phase 1)
"""
from fastapi import APIRouter, Depends

from app.db.session import get_session
from app.pydantic_schemas.project import Project

from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/projects", response_model=Project, status_code=201)  # Created
async def create_project(project: Project, session: Session = Depends(get_session)):
    # Implementation for creating a new project
    return {"message": f"Project {project.name} created successfully"}


@router.get("/projects", response_model=list[Project], status_code=200)  # OK
async def get_projects(session: Session = Depends(get_session)):
    # You are officially connected!
    # You can now run queries like: db.query(YourModel).all()
    return {"status": "Connected to the database successfully!"}


@router.get("/project/{project_id}/info", status_code=200)
async def get_project_info(project_id: int):
    return {"message": f"Project info for project {project_id}"}


@router.put("/project/{project_id}/info", status_code=200)
async def put_project_info(project_id: int, name: str, description: str):
    return {"message": f"Project {project_id} updated with name: {name} and description: {description}"}


@router.delete("/project/{project_id}", status_code=204)  # No Content
async def delete_project(project_id: int):
    # only by the projects owner
    return {"message": f"Project {project_id} deleted"}


@router.post("/project/{project_id}/invite?user={login}", status_code=200)
async def invite_user(project_id: int, login: str):
    # if project_owner != current_user:
    #    return {"error": "Only project owner can invite users"}
    return {"message": f"User {login} invited to project {project_id}"}


# Optional
@router.get("/project/{project_id}/share?with={email}", status_code=200)
async def share_project(project_id: int, email: str):
    # if project_owner != current_user:
    #    return {"error": "Only project owner can share the project"}
    return {"message": f"Project {project_id} shared with {email}"}
