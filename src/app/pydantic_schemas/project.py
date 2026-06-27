# src/app/pydantic_schemas/project.py
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from typing import Annotated
from datetime import datetime

from app.pydantic_schemas.document import DocumentOut
from app.pydantic_schemas.user import UserOut


class ProjectCreate(BaseModel):  # for POST requests, to create a new project
    name: Annotated[str, Field(min_length=4, max_length=100)]
    description: Annotated[str, Field(max_length=200)]

   # to avoid | None issues we declare without Annotation, we use default_factory to create empty lists and dicts, so not 1 mutual gets modified across instances
    invited_users: list[UserOut] | None = Field(default_factory=list)
    documents: list[DocumentOut] | None = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProjectUpdate(BaseModel):  # for PUT requests, to update the project data
    name: Annotated[str, Field(min_length=4, max_length=100)] | None = None
    description: Annotated[str, Field(max_length=200)] | None = None

    invited_users: list[UserOut] | None = Field(default_factory=list)
    documents: list[DocumentOut] | None = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProjectOut(BaseModel):  # for GET requests, to return the project data
    id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    owner_id: PositiveInt
    description: Annotated[str, Field(max_length=200)]

    invited_users: list[UserOut] | None = Field(default_factory=list)
    documents: list[DocumentOut] | None = Field(default_factory=list)

    updated_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
