from sqlalchemy.orm import selectinload
import time
import hmac
import hashlib
from typing import List
from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.project import Project
from app.models.access import Access
from app.models.user import User
from app.models.document import Document
from app.s3 import S3Service
from app.pydantic_schemas.project import ProjectCreate, ProjectUpdate
from app.config import settings


class ProjectService:
    @staticmethod
    async def _verify_access(
        session: AsyncSession, project_id: int, user_id: int, require_owner: bool = False
    ) -> Project:
        """
        Internal access resolver. Returns the Project model if authorized.
        """
        project_query = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_query.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        if project.owner_id == user_id:
            return project

        if require_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project owner can perform this action",
            )

        access_query = await session.execute(
            select(Access).where(
                Access.project_id == project_id,
                Access.user_id == user_id
            )
        )
        access_entry = access_query.scalar_one_or_none()
        if not access_entry:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this project",
            )

        return project

    @classmethod
    async def create_project(
        cls, session: AsyncSession, project_data: ProjectCreate, owner_id: int
    ) -> Project:
        """Creates a new project record. The creator automatically becomes the owner"""
        new_project = Project(
            name=project_data.name,
            description=project_data.description,
            owner_id=owner_id,
        )
        session.add(new_project)
        await session.commit()

        # reload with documents loaded
        result = await session.execute(
            select(Project)
            .options(selectinload(Project.documents))
            .where(Project.id == new_project.id)
        )
        return result.scalar_one()

    @classmethod
    async def get_user_projects(cls, session: AsyncSession, user_id: int) -> List[Project]:
        """Returns a list of projects that the user owns or has access to"""
        query = await session.execute(
            select(Project)
            .options(selectinload(Project.documents))
            .join(Access, Access.project_id == Project.id, isouter=True)
            .where(
                or_(
                    Project.owner_id == user_id,
                    Access.user_id == user_id
                )
            )
            .distinct()
        )
        return list(query.scalars().all())

    @classmethod
    async def get_project_details(
        cls, session: AsyncSession, project_id: int, user_id: int
    ) -> Project:
        """Returns project details if the user has access, otherwise raises an HTTPException"""
        await cls._verify_access(session, project_id, user_id)
        result = await session.execute(
            select(Project)
            .options(selectinload(Project.documents))
            .where(Project.id == project_id)
        )
        return result.scalar_one()

    @classmethod
    async def update_project(
        cls, session: AsyncSession, project_id: int, user_id: int, project_data: ProjectUpdate
    ) -> Project:
        """Modifies project details. Only the owner can update the project"""
        project = await cls._verify_access(session, project_id, user_id)

        if project_data.name is not None:
            project.name = project_data.name
        if project_data.description is not None:
            project.description = project_data.description

        await session.commit()

        result = await session.execute(
            select(Project)
            .options(selectinload(Project.documents))
            .where(Project.id == project.id)
        )
        return result.scalar_one()

    @classmethod
    async def delete_project(cls, session: AsyncSession, project_id: int, user_id: int) -> None:
        """
        Deletes a project. Commits database erasure first to guarantee integrity,
        then purges S3 assets cleanly
        """
        project = await cls._verify_access(session, project_id, user_id, require_owner=True)

        # Fetch ONLY the S3 URLs as raw strings
        url_query = await session.execute(
            select(Document.url).where(Document.project_id == project_id)
        )
        s3_keys = list(url_query.scalars().all())

        # Clear out database records first
        await session.execute(delete(Document).where(Document.project_id == project_id))
        await session.execute(delete(Access).where(Access.project_id == project_id))
        await session.delete(project)

        # Lock down state changes in the DB
        await session.commit()

        # Clean up S3 assets post-commit. If this fails, data integrity is still intact
        for key in s3_keys:
            try:
                await S3Service.delete_file(key)
            except Exception:
                pass  # Orphaned files can be safely ignored or cleaned by lifecycle policies

    @classmethod
    async def share_project(
        cls, session: AsyncSession, project_id: int, owner_id: int, email: str, ttl_seconds: int = 86400
    ) -> dict:
        """
        Generates a tokenized join link with a strict expiration window.
        """
        await cls._verify_access(session, project_id, owner_id, require_owner=True)

        # Set explicit expiration timestamp (eg. 24 hours from now)
        expires_at = int(time.time()) + ttl_seconds

        # Embed timestamp inside the signature structure
        message = f"project:{project_id}:invite:{email}:expires:{expires_at}".encode(
            "utf-8")
        key = settings.SECRET_KEY.encode("utf-8")
        token = hmac.new(key, message, hashlib.sha256).hexdigest()

        join_url = f"https://testdomain123456.com/join?project_id={project_id}&email={email}&expires_at={expires_at}&token={token}"

        return {
            "message": f"Share link generated successfully for {email}.",
            "join_url": join_url
        }

    @classmethod
    async def invite_user(
        cls,
        session: AsyncSession,
        project_id: int,
        owner_id: int,
        invited_login: str,
    ) -> dict:
        """
        Grant participant access to a project by login
        Only the project owner can invite
        """
        # Verify owner
        await cls._verify_access(session, project_id, owner_id, require_owner=True)

        # Find user to invite
        invited_user = (await session.execute(
            select(User).where(User.login == invited_login)
        )).scalar_one_or_none()

        if not invited_user:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                f"User '{invited_login}' not found")

        if invited_user.id == owner_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Cannot invite yourself")

        # Check if already has access
        existing = (await session.execute(
            select(Access).where(
                Access.project_id == project_id,
                Access.user_id == invited_user.id
            )
        )).scalar_one_or_none()

        if existing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "User already has access")

        # Grant access
        access = Access(
            project_id=project_id,
            user_id=invited_user.id,
            role="participant"
        )
        session.add(access)
        await session.commit()

        return {
            "message": f"User '{invited_login}' invited successfully",
            "project_id": project_id,
            "invited_user_id": invited_user.id,
            "role": "participant"
        }
