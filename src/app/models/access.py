from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
# avoid circular import
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Project


class Access(Base):
    __tablename__ = "access"

    __table_args__ = (UniqueConstraint(         # avoid same user having multiple access entries for the same project
        "user_id", "project_id", name="uq_user_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"),
                                         nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey(
        "projects.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="access_entries")
    project: Mapped[Project] = relationship(
        "Project", back_populates="access_entries")
