from pydantic import BaseModel


class TokenOut(BaseModel):
    """Pydantic model for returning token data, for GET requests"""
    access_token: str
    token_type: str = "bearer"
