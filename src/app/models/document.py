from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datetime import datetime

from app.db.base import Base
from app.models.project import Project


class Document(Base):
    """Document model representing a document associated with a project"""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey(
        "users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey(
        "projects.id"), index=True, nullable=False)
    url: Mapped[str] = mapped_column(Text(), nullable=False)  # s3
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    # in bytes, for aws lambda to check if the file is too large
    size: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    project: Mapped["Project"] = relationship(
        "Project", back_populates="documents")
