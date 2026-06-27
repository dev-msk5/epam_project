# UserCreate/Update, UserOut and User Pydantic schemas for FastAPI
from datetime import datetime
from pydantic import BaseModel, Field, PositiveInt, ConfigDict, model_validator
from typing import Annotated


class UserCreate(BaseModel):
    """Pydantic model for creating a new user, for POST requests"""
    login: Annotated[str, Field(min_length=8, max_length=100)]
    password: Annotated[str, Field(min_length=8, max_length=100)]
    repeat_password: Annotated[str, Field(min_length=8, max_length=100)]

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.repeat_password:
            raise ValueError("Passwords do not match")
        return self

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Pydantic model for user login, for POST requests"""
    login: Annotated[str, Field(min_length=8, max_length=100)]
    password: Annotated[str, Field(min_length=8, max_length=100)]

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Pydantic model for updating an existing user, for PUT requests"""
    login: Annotated[str, Field(max_length=100)] | None = None
    password: Annotated[str, Field(min_length=8, max_length=100)] | None = None

   # to avoid | None issues we declare without Annotation, we use default_factory to create empty lists and dicts, so not 1 mutual gets modified across instances
    projects: list | None = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    """Pydantic model for returning user data, for GET requests"""
    id: PositiveInt
    login: Annotated[str, Field(max_length=100)]

    # same as UserUpdate default_factory
    projects: list | None = Field(default_factory=list)

    updated_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
