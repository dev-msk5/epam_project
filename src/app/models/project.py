from sqlalchemy.orm import relationship

from app.db.base import Base
from sqlalchemy import Column, ForeignKey, Integer, String


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"),
                      index=True, nullable=False)
    description = Column(String, index=True, nullable=False)

    # relationship to owner (User)
    owner = relationship("User", back_populates="projects")

    # relationship to documents (one-to-many)
    documents = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan")

# class Project(Base):
#     documents: Mapped[list["Document"]] = relationship(
#         back_populates="project",
#         cascade="all, delete-orphan"   # cleans up automatically
#     )
