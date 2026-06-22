from app.db.base import Base
from sqlalchemy import Column, Integer, String


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner = Column(String, index=True)
    description = Column(String, index=True)
    invited_users = Column(list, default=[])
    documents = Column(list, default=[])
