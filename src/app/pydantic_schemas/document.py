from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class DocumentCreate(BaseModel):
    """Pydantic model for creating a new document, for POST requests"""

    name: Annotated[str, Field(min_length=4, max_length=100)]
    project_id: PositiveInt

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    """Pydantic model for updating document data, for PUT requests"""

    name: Annotated[str, Field(min_length=4, max_length=100)] | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    """Pydantic model for returning document data, for GET requests"""

    id: PositiveInt
    owner_id: PositiveInt
    name: Annotated[str, Field(max_length=100)]
    project_id: PositiveInt

    # Map the DB column 'url' to the public property 's3_key'
    s3_key: str = Field(..., validation_alias="url")
    size: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentDownloadOut(DocumentOut):
    """Pydantic model for returning document data with download URL, for GET requests"""

    # Dedicated secure public URL parameter
    download_url: str
