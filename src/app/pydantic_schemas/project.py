#  ProjectCreate, ProjectUpdate, ProjectOut
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from typing import Annotated


class Project(BaseModel):  # ProjectOut is the same
    id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    owner_id: PositiveInt
    description: Annotated[str, Field(max_length=200)]
    invited_users: Annotated[list, Field(default_factory=list)]
    documents: Annotated[list, Field(default_factory=list)]

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: Annotated[str, Field(max_length=100)]
    description: Annotated[str, Field(max_length=200)]

    model_config = ConfigDict(from_attributes=True)


class ProjectUpdate(BaseModel):
    name: Annotated[str, Field(max_length=100)] | None = None
    description: Annotated[str, Field(max_length=200)] | None = None

    model_config = ConfigDict(from_attributes=True)
