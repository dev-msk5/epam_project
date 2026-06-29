from pydantic import BaseModel, ConfigDict


class TokenOut(BaseModel):
    """Pydantic model for returning token data, for GET requests"""

    access_token: str
    token_type: str = "bearer"

    model_config = ConfigDict(from_attributes=True)
