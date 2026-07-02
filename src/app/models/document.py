from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Document(Base):
    """Document model representing a document associated with a project"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(Text(), nullable=False)  # holds S3 key
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    size: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    # State tracking to prevent zombie records and read leaks
    is_pending: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    project: Mapped["Project"] = relationship("Project", back_populates="documents")
