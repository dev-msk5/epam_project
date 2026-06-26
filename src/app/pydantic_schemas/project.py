#  ProjectCreate, ProjectUpdate, ProjectOut
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from typing import Annotated
from datetime import datetime


class ProjectCreate(BaseModel):

    name: Annotated[str, Field(max_length=100)]
    description: Annotated[str, Field(max_length=200)]
    invited_users: Annotated[list, Field(default_factory=list)] | None = None
    documents: Annotated[list, Field(default_factory=list)] | None = None

    # automated parts
    owner_id: PositiveInt
    id: PositiveInt
    created_at: Annotated[datetime, Field(default_factory=datetime.now)]

    model_config = ConfigDict(from_attributes=True)


class ProjectUpdate(BaseModel):
    name: Annotated[str, Field(max_length=100)] | None = None
    description: Annotated[str, Field(max_length=200)] | None = None
    invited_users: Annotated[list, Field(default_factory=list)] | None = None
    documents: Annotated[list, Field(default_factory=list)] | None = None

    # automated parts
    updated_at: Annotated[datetime, Field(
        default_factory=datetime.now)] | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectOut(BaseModel):  # ProjectOut is the same
    id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    owner_id: PositiveInt
    description: Annotated[str, Field(max_length=200)]
    invited_users: Annotated[list, Field(default_factory=list)] | None = None
    documents: Annotated[list, Field(default_factory=list)] | None = None
    updated_at: Annotated[datetime, Field(
        default_factory=datetime.now)] | None = None
    created_at: datetime

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)
