from pydantic_settings import BaseSettings, SettingsConfigDict
# Pydantic settings, reads from .env

# Test that constants are matching the .env file, and that they are read correctly by Pydantic ?


class Settings(BaseSettings):
    # Read from environment; no default to force providing it in .env or env vars
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None
    AWS_REGION: str = "us-east-1"

    model_config = SettingsConfigDict(
        env_file=".env",        # where to find the constants
        env_file_encoding="utf-8",  # how to read them, like encoding
        extra="ignore",          # what to do with unknown env vars ? silently ignore
    )


settings = Settings()
