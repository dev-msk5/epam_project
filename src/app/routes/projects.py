"""
- POST /projects                      (Create project)
 - GET /projects                       (Get all accessible projects)
 - GET /project/<project_id>/info      (Get project details)
 - PUT /project/<project_id>/info      (Update project details)
 - DELETE /project/<project_id>        (Delete project)
 - POST /project/<project_id>/invite?user=<login>  (Grant access to user)

 - GET /project/<project_id>/share?with=<email>   
 (Send share link via email - Optional Phase 1)
"""

from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.pydantic_schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.project import ProjectService

router = APIRouter()


@router.post(
    "/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED
)
async def create_project(
    project: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new project and return the created project data"""
    return await ProjectService.create_project(
        session=session, project_data=project, owner_id=current_user.id
    )


@router.get(
    "/projects", response_model=List[ProjectOut], status_code=status.HTTP_200_OK
)
async def get_projects(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all projects accessible to the current user"""
    return await ProjectService.get_user_projects(
        session=session, user_id=current_user.id
    )


@router.get(
    "/project/{project_id}/info",
    response_model=ProjectOut,
    status_code=status.HTTP_200_OK,
)
async def get_project_info(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information about a specific project"""
    return await ProjectService.get_project_details(
        session=session, project_id=project_id, user_id=current_user.id
    )


@router.put(
    "/project/{project_id}/info",
    response_model=ProjectOut,
    status_code=status.HTTP_200_OK,
)
async def put_project_info(
    project_id: int,
    project_data: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a specific project. Only the owner can update the project"""
    return await ProjectService.update_project(
        session=session,
        project_id=project_id,
        user_id=current_user.id,
        project_data=project_data,
    )


@router.delete(
    "/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def delete_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific project. Only the owner can delete the project"""
    await ProjectService.delete_project(
        session=session, project_id=project_id, user_id=current_user.id
    )
    return None


@router.post("/project/{project_id}/invite", status_code=status.HTTP_200_OK)
async def invite_user(
    project_id: int,
    login: str = Query(..., alias="user"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Invite a user to a project by their login. Only the project owner can invite"""
    await ProjectService.invite_user(
        session=session,
        project_id=project_id,
        owner_id=current_user.id,
        invited_login=login,
    )
    return {"message": f"User {login} invited to project {project_id}"}


@router.get("/project/{project_id}/share", status_code=status.HTTP_200_OK)
async def share_project(
    project_id: int,
    email: str = Query(..., alias="with"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Generate a share link for a project and send it via email. 
    Only the project owner can share"""
    # Optional Phase 1 tokenized share path
    return await ProjectService.share_project(
        session=session, project_id=project_id, owner_id=current_user.id, email=email
    )
