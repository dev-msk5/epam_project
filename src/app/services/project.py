# create, delete, share, access checks

from sqlalchemy.ext.asyncio import AsyncSession
from app.pydantic_schemas.project import Project
from app.models import Project as ProjectModel


async def create_project(project: Project, session: AsyncSession):
    "Implementation for creating a new project from Pydantic schema to database model and saving it to the database"
    try:
        db_project = ProjectModel(
            name=project.name, description=project.description)
        session.add(db_project)
        await session.commit()
        await session.refresh(db_project)
    except Exception as e:
        await session.rollback()
        raise e
    return {"message": f"Project {db_project.name} created successfully"}
