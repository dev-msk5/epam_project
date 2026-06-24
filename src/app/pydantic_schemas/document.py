# DocumentOut, DocumentUpdate
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field, PositiveInt, ConfigDict


class Document(BaseModel):
    id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    project_id: PositiveInt
    url: Annotated[str, Field(max_length=200)]
    created_at: Annotated[datetime, Field(default_factory=datetime.now)]
    updated_at: Annotated[datetime, Field(default_factory=datetime.now)]

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)
