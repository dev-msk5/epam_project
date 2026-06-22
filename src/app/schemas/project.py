#  ProjectCreate, ProjectUpdate, ProjectOut
from pydantic import BaseModel


class Project(BaseModel):
    id: int
    name: str
    owner: str
    description: str
    invited_users: list = []
    documents: list = []
