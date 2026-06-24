from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.pydantic_schemas.project import Project


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, nullable=False)
    login: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)

    # one-to-many relationship to projects
    projects: Mapped[list[Project]] = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('LENGTH(login) >= 8', name='login_min_length'),
        CheckConstraint('LENGTH(hashed_password) >= 8',
                        name='password_min_length'),
    )
