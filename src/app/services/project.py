from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.project import Project
from app.models.user import User
from app.models.access import Access
from app.pydantic_schemas.project import ProjectCreate, ProjectUpdate


async def _get_access(project_id: int, user_id: int, session: AsyncSession) -> Access | None:
    result = await session.execute(
        select(Access).where(
            Access.project_id == project_id,
            Access.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def create_project(data: ProjectCreate, owner: User, session: AsyncSession) -> Project:
    db_project = Project(
        name=data.name,
        description=data.description,
        owner_id=owner.id
    )
    session.add(db_project)
    await session.flush()

    access = Access(user_id=owner.id, project_id=db_project.id, role="owner")
    session.add(access)
    await session.commit()
    await session.refresh(db_project)
    return db_project


async def get_projects(user: User, session: AsyncSession) -> list[Project]:
    result = await session.execute(
        select(Project)
        .join(Access, Access.project_id == Project.id)
        .where(Access.user_id == user.id)
        .options(selectinload(Project.documents))
    )
    return result.scalars().all()


async def get_project_by_id(project_id: int, user: User, session: AsyncSession) -> Project:
    access = await _get_access(project_id, user.id, session)
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def update_project(project_id: int, data: ProjectUpdate, user: User, session: AsyncSession) -> Project:
    access = await _get_access(project_id, user.id, session)
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description

    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(project_id: int, user: User, session: AsyncSession) -> None:
    access = await _get_access(project_id, user.id, session)
    if not access or access.role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the owner can delete this project")

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # S3 document deletion will be added when document service is ready
    await session.delete(project)
    await session.commit()


async def invite_user(project_id: int, login: str, owner: User, session: AsyncSession) -> None:
    access = await _get_access(project_id, owner.id, session)
    if not access or access.role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the owner can invite users")

    result = await session.execute(select(User).where(User.login == login))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await _get_access(project_id, target_user.id, session)
    if existing:
        raise HTTPException(status_code=409, detail="User already has access")

    new_access = Access(user_id=target_user.id,
                        project_id=project_id, role="participant")
    session.add(new_access)
    await session.commit()
