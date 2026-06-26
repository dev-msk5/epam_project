# UserCreate/Update, UserOut and User Pydantic schemas for FastAPI
from datetime import datetime

from pydantic import BaseModel, Field, PositiveInt, ConfigDict, model_validator
from typing import Annotated


class UserCreate(BaseModel):  # for POST requests, to create a new user
    login: Annotated[str, Field(min_length=8, max_length=100)]
    password: Annotated[str, Field(min_length=8, max_length=100)]
    repeat_password: Annotated[str, Field(min_length=8, max_length=100)]
    # projects: Annotated[list, Field(default_factory=list)] | None = None

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.repeat_password:
            raise ValueError("Passwords do not match")
        return self

    # automated parts
    # id: PositiveInt

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):  # for PUT requests, to update the user data
    login: Annotated[str, Field(max_length=100)] | None = None
    password: Annotated[str, Field(min_length=8, max_length=100)] | None = None
    projects: Annotated[list, Field(default_factory=list)] | None = None

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):  # for GET requests, to return the user data
    id: PositiveInt
    login: Annotated[str, Field(max_length=100)]
    projects: Annotated[list, Field(default_factory=list)] | None = None
    updated_at: datetime | None = None
    created_at: datetime

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)
