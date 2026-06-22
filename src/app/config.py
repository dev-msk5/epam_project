from pydantic_settings import BaseSettings
# Pydantic settings, reads from .env


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
