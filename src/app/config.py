import os

from pydantic_settings import BaseSettings, SettingsConfigDict


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


# SSM LOAD FOR EC2 COMPATIBILITY
ssm_data = {}
if os.getenv("USE_SSM", "false").lower() in ("true", "1", "yes"):
    try:
        import boto3

        aws_region = os.getenv("AWS_REGION", "us-east-1")
        ssm_path = os.getenv("SSM_PATH", "/project-dashboard/prod/")

        # Fetch SSM parameters recursively under /project-dashboard/prod/
        ssm = boto3.client("ssm", region_name=aws_region)
        response = ssm.get_parameters_by_path(
            Path=ssm_path, WithDecryption=True, Recursive=True
        )

        for param in response.get("Parameters", []):
            # Extract key name
            # (e.g., "/project-dashboard/prod/DATABASE_URL" -> "DATABASE_URL")
            key = param["Name"].split("/")[-1]
            ssm_data[key] = param["Value"]

    except Exception as e:
        # Fails silently to prevent crashing during local setup/testing
        # if AWS is not reached
        print(f"Warning: Failed to load SSM parameters from path {ssm_path}: {e}")

# If SSM is active, pass retrieved parameters as overrides during Settings instantiation
# Otherwise, falls back directly to the local .env file.
settings = Settings(**ssm_data)
