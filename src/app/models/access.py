from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import Project


class Access(Base):
    __tablename__ = "access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"),
                                         nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"),
                                            nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["User"] = relationship(
        "User", back_populates="access_entries")
    project: Mapped["Project"] = relationship(
        "Project", back_populates="access_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project"),
    )
