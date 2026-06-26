from app.db.base import Base
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.project import Project


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey(
        "users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey(
        "projects.id"), index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(200), nullable=False)  # s3
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)

    project: Mapped[Project] = relationship(
        "Project", back_populates="documents")
