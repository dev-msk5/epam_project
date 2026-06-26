#  ProjectCreate, ProjectUpdate, ProjectOut
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from typing import Annotated
from datetime import datetime

from app.pydantic_schemas.document import DocumentOut
from app.pydantic_schemas.user import UserOut


class ProjectCreate(BaseModel):  # for POST requests, to create a new project

    name: Annotated[str, Field(min_length=4, max_length=100)]
    description: Annotated[str, Field(max_length=200)]
    invited_users: Annotated[list[UserOut], Field(
        default_factory=list)] | None = None
    documents: Annotated[list[DocumentOut], Field(
        default_factory=list)] | None = None

    # automated parts
    # owner_id: PositiveInt # assigned automatically from the current user, ntot input from the user
    # id: PositiveInt

    model_config = ConfigDict(from_attributes=True)


class ProjectUpdate(BaseModel):  # for PUT requests, to update the project data
    name: Annotated[str, Field(min_length=4, max_length=100)] | None = None
    description: Annotated[str, Field(max_length=200)] | None = None
    invited_users: Annotated[list[UserOut], Field(
        default_factory=list)] | None = None
    documents: Annotated[list[DocumentOut], Field(
        default_factory=list)] | None = None

    # updated_at: DB side

    model_config = ConfigDict(from_attributes=True)


class ProjectOut(BaseModel):  # for GET requests, to return the project data
    id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    owner_id: PositiveInt
    description: Annotated[str, Field(max_length=200)]
    invited_users: Annotated[list[UserOut], Field(
        default_factory=list)] | None = None
    documents: Annotated[list[DocumentOut], Field(
        default_factory=list)] | None = None
    updated_at: datetime | None = None
    created_at: datetime

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)
