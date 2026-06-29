# src/app/pydantic_schemas/user.py

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


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

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    """Pydantic model for returning user data, for GET requests"""

    id: PositiveInt
    login: Annotated[str, Field(max_length=100)]
    created_at: datetime
    updated_at: datetime | None = None
    # If you need projects, use ProjectOut schema instead

    model_config = ConfigDict(from_attributes=True)
