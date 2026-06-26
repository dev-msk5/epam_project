from datetime import datetime, time, timezone
from typing import Annotated

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, DateTime

from app.db.base import Base

from app.pydantic_schemas.document import Document
from app.pydantic_schemas.user import User


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"),
                                          index=True, nullable=False)
    description: Mapped[str] = mapped_column(
        String(200), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, onupdate=datetime.now(time.zone.utc))

    # relationship to owner (User)
    owner: Mapped["User"] = relationship("User", back_populates="projects")

    # relationship to documents (one-to-many)
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan")
