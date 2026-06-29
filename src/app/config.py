from pydantic_settings import BaseSettings, SettingsConfigDict

# Pydantic settings, reads from .env
# Keep this aligned with the .env file


class Settings(BaseSettings):
    """Read configuration from environment variables and .env files"""

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None
    AWS_REGION: str = "us-east-1"
    PROJECT_STORAGE_LIMIT_BYTES: int = 524288000

    model_config = SettingsConfigDict(
        env_file=".env",  # where to find the constants
        env_file_encoding="utf-8",  # how to read them
        extra="ignore",  # ignore unknown env vars
    )


settings = Settings()
