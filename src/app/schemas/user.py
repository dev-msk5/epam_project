# UserCreate, UserOut
from pydantic import BaseModel


class User(BaseModel):
    id: int
    login: str
    password: str
    projects: list = []
