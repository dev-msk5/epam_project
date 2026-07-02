from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Access(Base):
    """Relationship between users and projects with a per-project role"""

    __tablename__ = "access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="access_entries")
    project: Mapped["Project"] = relationship(
        "Project", back_populates="access_entries"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project"),
        # guard against typos in role assignment, allow 'owner' or 'participant'
        CheckConstraint(
            "role IN ('owner', 'participant')",
            name="ck_role_valid",
        ),
    )

    @classmethod
    async def get_role_for_project(
        cls,
        session: AsyncSession,
        project_id: int,
        user_id: int,
    ) -> str | None:
        """Return the stored role for a user on a project, if any."""
        result = await session.execute(
            select(cls.role).where(
                cls.project_id == project_id,
                cls.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
