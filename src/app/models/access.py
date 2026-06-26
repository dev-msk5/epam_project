from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.project import Project
from app.models.user import User


class Access(Base):
    __tablename__ = "access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"),
                                         nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey(
        "projects.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=True)

    user: Mapped[User] = relationship("User", backref="access_entries")
    project: Mapped[Project] = relationship(
        "Project", backref="access_entries")
