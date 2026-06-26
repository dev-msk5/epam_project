# DocumentOut, DocumentUpdate
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field, PositiveInt, ConfigDict


class DocumentCreate(BaseModel):
    name: Annotated[str, Field(max_length=100)]
    url: Annotated[str, Field(max_length=200)]  # s3

    # automated parts
    owner_id: PositiveInt
    id: PositiveInt
    project_id: PositiveInt
    created_at: Annotated[datetime, Field(
        default_factory=datetime.now)]  # automate it, def factory for same {},[] problem with different instances of class

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    name: Annotated[str, Field(max_length=100)] | None = None
    url: Annotated[str, Field(max_length=200)] | None = None  # s3

    # automated parts
    updated_at: Annotated[datetime, Field(default_factory=datetime.now)]

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: PositiveInt
    owner_id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    project_id: PositiveInt
    url: Annotated[str, Field(max_length=200)]  # s3
    created_at: datetime
    updated_at: datetime

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)
