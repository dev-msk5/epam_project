from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, CheckConstraint
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.access import Access


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    login: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan"
    )
    access_entries: Mapped[list["Access"]] = relationship(
        "Access", back_populates="user"
    )

    __table_args__ = (
        CheckConstraint('LENGTH(login) >= 8', name='login_min_length'),
    )
