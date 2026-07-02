import hashlib
import hmac
import logging
import time
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.access import Access
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.pydantic_schemas.project import ProjectCreate, ProjectUpdate
from app.s3 import S3Service

# Initialize app logger
logger = logging.getLogger("app_logger")


class ProjectService:
    @staticmethod
    async def _resolve_access(
        session: AsyncSession,
        project_id: int,
        user_id: int,
        require_owner: bool = False,
        project: Project | None = None,
    ) -> tuple[Project, str]:
        """
        Internal access resolver. Returns the Project model and role if authorized.
        """
        if project is None:
            project_query = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = project_query.scalar_one_or_none()
        if project is None:
            logger.warning(f"Project not found: ID {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        role = await Access.get_role_for_project(session, project_id, user_id)
        if role is None:
            logger.warning(
                f"Access denied: User {user_id} requested Project {project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this project",
            )

        if require_owner and role != "owner":
            logger.warning(
                f"Permission denied: User {user_id} is not the owner of Project {project_id}"  # noqa: E501
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project owner can perform this action",
            )

        return project, role

    @classmethod
    async def create_project(
        cls, session: AsyncSession, project_data: ProjectCreate, owner_id: int
    ) -> Project:
        """
        Creates a new project and its owner Access row atomically
        """
        logger.info(f"User {owner_id} is creating project: {project_data.name}")

        new_project = Project(
            name=project_data.name,
            description=project_data.description,
        )
        session.add(new_project)
        await session.flush()  # assigns new_project.id without committing

        owner_access = Access(
            project_id=new_project.id,
            user_id=owner_id,
            role="owner",
        )
        session.add(owner_access)

        # Single commit point, if anything above raised, nothing here runs,
        # and get_session's context-manager close() rolls back the whole
        # (still-open) transaction, so no orphan project or dangling access row.
        await session.commit()

        result = await session.execute(
            select(Project)
            .options(
                selectinload(Project.documents), selectinload(Project.access_entries)
            )
            .where(Project.id == new_project.id)
        )
        logger.info(f"Project {new_project.id} successfully created by User {owner_id}")
        return result.scalar_one()

    @classmethod
    async def get_user_projects(
        cls, session: AsyncSession, user_id: int
    ) -> List[Project]:
        """Returns a list of projects that the user owns or has access to"""
        query = await session.execute(
            select(Project)
            .options(
                selectinload(Project.documents), selectinload(Project.access_entries)
            )
            .join(Access, Access.project_id == Project.id)
            .where(Access.user_id == user_id)
            .distinct()
        )
        return list(query.scalars().all())

    @classmethod
    async def get_project_details(
        cls, session: AsyncSession, project_id: int, user_id: int
    ) -> Project:
        """Returns project details if the user has access,
        otherwise raises an HTTPException"""
        await cls._resolve_access(session, project_id, user_id)
        result = await session.execute(
            select(Project)
            .options(
                selectinload(Project.documents), selectinload(Project.access_entries)
            )
            .where(Project.id == project_id)
        )
        return result.scalar_one()

    @classmethod
    async def update_project(
        cls,
        session: AsyncSession,
        project_id: int,
        user_id: int,
        project_data: ProjectUpdate,
    ) -> Project:
        """Modifies project details. Participants can modify, but cannot delete"""
        project, _ = await cls._resolve_access(session, project_id, user_id)

        logger.info(f"User {user_id} is updating project: {project_id}")
        if project_data.name is not None:
            project.name = project_data.name
        if project_data.description is not None:
            project.description = project_data.description

        await session.commit()

        result = await session.execute(
            select(Project)
            .options(
                selectinload(Project.documents), selectinload(Project.access_entries)
            )
            .where(Project.id == project.id)
        )
        logger.info(f"Project {project_id} successfully updated by User {user_id}")
        return result.scalar_one()

    @classmethod
    async def delete_project(
        cls, session: AsyncSession, project_id: int, user_id: int
    ) -> None:
        """
        Deletes a project. Commits database erasure first to guarantee integrity,
        then purges S3 assets cleanly
        """
        project, _ = await cls._resolve_access(
            session, project_id, user_id, require_owner=True
        )

        logger.info(f"User {user_id} requested deletion of Project {project_id}")

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
        logger.info(f"Project {project_id} and metadata successfully cleared from DB")

        # Clean up S3 assets post-commit. If this fails, data integrity is still intact
        for key in s3_keys:
            try:
                await S3Service.delete_file(key)
                logger.info(f"S3 file deleted successfully: {key}")
            except Exception as e:
                logger.warning(
                    f"Failed to delete S3 file: {key} during project deletion | Error: {str(e)}"  # noqa: E501
                )

    @classmethod
    async def share_project(
        cls,
        session: AsyncSession,
        project_id: int,
        owner_id: int,
        email: str,
        ttl_seconds: int = 86400,
    ) -> dict:
        """
        Generates a tokenized join link with a strict expiration window
        """
        await cls._resolve_access(session, project_id, owner_id, require_owner=True)

        logger.info(
            f"User {owner_id} is generating a share token for {email} on Project {project_id}"  # noqa: E501
        )

        # Set explicit expiration timestamp (eg. 24 hours from now)
        expires_at = int(time.time()) + ttl_seconds

        # Embed timestamp inside the signature structure
        message = f"project:{project_id}:invite:{email}:expires:{expires_at}".encode(
            "utf-8"
        )
        key = settings.SECRET_KEY.encode("utf-8")
        token = hmac.new(key, message, hashlib.sha256).hexdigest()

        join_url = f"https://testdomain123456.com/join?project_id={project_id}&email={email}&expires_at={expires_at}&token={token}"

        logger.info(
            f"Share link successfully generated for {email} on Project {project_id}"
        )
        return {
            "message": f"Share link generated successfully for {email}.",
            "join_url": join_url,
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
        await cls._resolve_access(session, project_id, owner_id, require_owner=True)

        logger.info(
            f"User {owner_id} is inviting '{invited_login}' to Project {project_id}"
        )

        # Find user to invite
        invited_user = (
            await session.execute(select(User).where(User.login == invited_login))
        ).scalar_one_or_none()

        if not invited_user:
            # User does not exist
            logger.warning(f"Failed to invite user: '{invited_login}' does not exist")
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"User '{invited_login}' not found"
            )

        if invited_user.id == owner_id:
            # Self invite check
            logger.warning(
                f"User {owner_id} attempted to self-invite to Project {project_id}"
            )
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot invite yourself")

        # Check if already has access
        existing = (
            await session.execute(
                select(Access).where(
                    Access.project_id == project_id, Access.user_id == invited_user.id
                )
            )
        ).scalar_one_or_none()

        if existing:
            logger.warning(
                f"User '{invited_login}' already has access to Project {project_id}"
            )
            raise HTTPException(status.HTTP_409_CONFLICT, "User already has access")

        # Grant access
        access = Access(
            project_id=project_id, user_id=invited_user.id, role="participant"
        )
        session.add(access)
        await session.commit()

        logger.info(
            f"User '{invited_login}' successfully joined Project {project_id} as participant"  # noqa: E501
        )
        return {
            "message": f"User '{invited_login}' invited successfully",
            "project_id": project_id,
            "invited_user_id": invited_user.id,
            "role": "participant",
        }
