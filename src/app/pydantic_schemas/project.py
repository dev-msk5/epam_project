# src/app/pydantic_schemas/project.py
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.pydantic_schemas.document import DocumentOut


class ProjectCreate(BaseModel):
    """Pydantic model for creating a new project, for POST requests"""

    name: Annotated[str, Field(min_length=4, max_length=100)]
    description: Annotated[str, Field(max_length=200)]

    model_config = ConfigDict(from_attributes=True)


class ProjectUpdate(BaseModel):
    """Pydantic model for updating an existing project, for PUT requests"""

    name: Annotated[str, Field(min_length=4, max_length=100)] | None = None
    description: Annotated[str, Field(max_length=200)] | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectOut(BaseModel):
    """Pydantic model for returning project data, for GET requests"""

    id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    owner_id: PositiveInt
    description: Annotated[str, Field(max_length=200)]

    # to avoid | None issues we declare without Annotation and use default_factory
    # to create empty lists and dicts, not 1 mutual gets modified across instances
    documents: list[DocumentOut] | None = Field(default_factory=list)

    updated_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
