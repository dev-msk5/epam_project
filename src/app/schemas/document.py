# DocumentOut, DocumentUpdate
from pydantic import BaseModel


class Document(BaseModel):
    id: int
    name: str
    project_id: int
    url: str
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True
