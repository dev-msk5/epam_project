# src/app/pydantic_schemas/project.py
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

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

    @model_validator(mode="before")
    @classmethod
    def populate_owner_id(cls, value):
        if isinstance(value, dict):
            if "owner_id" in value:
                return value
            access_entries = value.get("access_entries") or []
        else:
            if getattr(value, "owner_id", None) is not None:
                return value
            access_entries = getattr(value, "access_entries", []) or []

        owner_id = None
        for access in access_entries:
            if getattr(access, "role", None) == "owner":
                owner_id = getattr(access, "user_id", None)
                break

        if owner_id is None:
            raise ValueError("Project owner could not be resolved from access entries")

        if isinstance(value, dict):
            value = dict(value)
            value["owner_id"] = owner_id
            return value

        setattr(value, "owner_id", owner_id)
        return value
