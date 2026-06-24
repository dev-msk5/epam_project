from pydantic_settings import BaseSettings
# Pydantic settings, reads from .env


class Settings(BaseSettings):
    # Read from environment; no default to force providing it in .env or env vars
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = ""

    # pydantic v2: use model_config to set env_file and extra handling
    model_config = {"env_file": ".env", "extra": "ignore"}

    class Config:
        env_file = ".env"


settings = Settings()
