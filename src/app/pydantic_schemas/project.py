#  ProjectCreate, ProjectUpdate, ProjectOut
from pydantic import BaseModel, Field, PositiveInt
from typing import Annotated


class Project(BaseModel):  # ProjectOut is the same
    id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    owner_id: PositiveInt
    description: Annotated[str, Field(max_length=200)]
    invited_users: Annotated[list, Field(default_factory=list)]
    documents: Annotated[list, Field(default_factory=list)]

    class Config:
        # When validating this model, accept objects with attributes (e.g. obj.id) as input
        from_attributes = True


class ProjectCreate(BaseModel):
    name: Annotated[str, Field(max_length=100)]
    description: Annotated[str, Field(max_length=200)]

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    name: Annotated[str, Field(max_length=100)] | None = None
    description: Annotated[str, Field(max_length=200)] | None = None

    class Config:
        from_attributes = True
