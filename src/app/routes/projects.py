"""
 - POST /projects                      (Create project)
  - GET /projects                       (Get all accessible projects)
  - GET /project/<project_id>/info      (Get project details)
  - PUT /project/<project_id>/info      (Update project details)
  - DELETE /project/<project_id>        (Delete project)
  - POST /project/<project_id>/invite?user=<login>  (Grant access to user)
  
  - GET /project/<project_id>/share?with=<email>   (Send share link via email - Optional Phase 1)
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.pydantic_schemas.project import ProjectCreate, ProjectOut

router = APIRouter()


# Created
@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(project: ProjectCreate, session: AsyncSession = Depends(get_session)):
    """Create a new project"""
    # TODO create a new project in the database
    # return matching ProjectOut schema structure
    return {
        "id": 1,
        "name": project.name,
        "owner_id": 1,
        "description": project.description,
        "created_at": datetime.now(timezone.utc)
    }


# OK
@router.get("/projects", response_model=list[ProjectOut], status_code=200)
async def get_projects(session: AsyncSession = Depends(get_session)):
    """Get all accessible projects for the current user"""
    # TODO fetch all projects accessible to the current user from the database
    # return a list matching ProjectOut schema structure
    return [
        {
            "id": 1,
            "name": "Demo Project",
            "owner_id": 1,
            "description": "Mock database connection success!",
            "created_at": datetime.now(timezone.utc)
        }
    ]


@router.get("/project/{project_id}/info", response_model=ProjectOut, status_code=200)
async def get_project_info(project_id: int):
    """Get detailed information about a specific project"""
    # TODO fetch project details from the database
    return {
        "id": project_id,
        "name": f"Project {project_id}",
        "owner_id": 1,
        "description": "Mock detailed description",
        "created_at": datetime.now(timezone.utc)
    }


@router.put("/project/{project_id}/info", response_model=ProjectOut, status_code=200)
async def put_project_info(project_id: int, name: str, description: str):
    """Update information for a specific project"""
    # TODO check if user has access to the project
    # TODO update project information in the database
    return {
        "id": project_id,
        "name": name,
        "owner_id": 1,
        "description": description,
        "created_at": datetime.now(timezone.utc)
    }


# No Content
@router.delete("/project/{project_id}", status_code=204)
async def delete_project(project_id: int):
    """Delete a specific project"""
    # TODO check if user has access to the project
    return None  # No body returned on 204


# returns a message string, if it was successful, otherwise raises an HTTPException with appropriate status code and message
@router.post("/project/{project_id}/invite", status_code=200)
async def invite_user(project_id: int, login: str = Query(..., alias="user")):
    """Invite a user to a specific project by their login"""
    # TODO check if user has access to the project
    return {"message": f"User {login} invited to project {project_id}"}


# Optional:  returns a message string
@router.get("/project/{project_id}/share", status_code=200)
async def share_project(project_id: int, email: str = Query(..., alias="with")):
    """Share a specific project with a user via email"""
    # TODO check if user has access to the project
    return {"message": f"Project {project_id} shared with {email}"}
