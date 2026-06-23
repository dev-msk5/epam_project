from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base


class Access(Base):
    __tablename__ = "access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"),
                     nullable=False, index=True)
    project_id = Column(Integer, ForeignKey(
        "projects.id"), nullable=False, index=True)
    role = Column(String, nullable=True)

    user = relationship("User", backref="access_entries")
    project = relationship("Project", backref="access_entries")
