# UserCreate/Update, UserOut and User Pydantic schemas for FastAPI
from pydantic import BaseModel, Field, PositiveInt, ConfigDict
from typing import Annotated


class UserCreate(BaseModel):
    login: Annotated[str, Field(min_length=8, max_length=100)]
    password: Annotated[str, Field(min_length=8, max_length=100)]
    projects: Annotated[list, Field(default_factory=list)] | None = None

    # automated parts
    id: PositiveInt

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    login: Annotated[str, Field(max_length=100)] | None = None
    password: Annotated[str, Field(min_length=8, max_length=100)] | None = None
    projects: Annotated[list, Field(default_factory=list)] | None = None

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: PositiveInt
    login: Annotated[str, Field(max_length=100)]
    password: Annotated[str, Field(min_length=8, max_length=100)]
    projects: Annotated[list, Field(default_factory=list)] | None

    # When validating this model, accept objects with attributes (e.g. obj.id) as input
    model_config = ConfigDict(from_attributes=True)
