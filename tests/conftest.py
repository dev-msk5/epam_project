import asyncio
import gc
import os
import socket
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.security import create_access_token, get_password_hash

# Database URL resolution


DATABASE_URL = settings.DATABASE_URL

if "postgresql+asyncpg://" in DATABASE_URL:
    base_url, db_name = DATABASE_URL.rsplit("/", 1)
    if (
        db_name == "test_db"
        or db_name.endswith("_test")
        or db_name.endswith("test")
    ):
        TEST_DATABASE_URL = DATABASE_URL
    else:
        TEST_DATABASE_URL = f"{base_url}/{db_name}_test"

    if "@db:" in TEST_DATABASE_URL or "@db/" in TEST_DATABASE_URL:
        try:
            socket.getaddrinfo("db", 5432)
        except socket.gaierror:
            TEST_DATABASE_URL = TEST_DATABASE_URL.replace(
                "@db:", "@localhost:"
            ).replace("@db/", "@localhost/")
else:
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DATABASE_URL)


# Engine - session-scoped, NullPool prevents cross-loop connection reuse


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """One engine for the whole session. NullPool = no connection is reused."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


# Schema lifecycle - drop/create once per session

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db(test_engine):
    """Drop + create all tables once at session start, drop at session end."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Per-test DB session, each test gets a fresh rollbacked transation

@pytest_asyncio.fixture  # function scope (default)
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Opens a connection, begins a transaction, yields a session bound to it,
    then rolls back - so every test starts with a clean slate.
    """
    async with test_engine.connect() as connection:
        await connection.begin()

        session_factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with session_factory() as session:
            yield session

        await connection.rollback()


# FastAPI dependency override

@pytest.fixture(autouse=True)
def override_dependencies(db_session: AsyncSession):
    """Swap get_session for the per-test rollback session on every test."""

    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


# Cleanup barrier

@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_event_loop_barrier():
    """Give asyncpg time to drain before the session loop closes."""
    yield
    gc.collect()
    await asyncio.sleep(0.1)


# HTTP client


@pytest_asyncio.fixture  # function scope - fresh per test
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# S3 mock


@pytest.fixture
def mock_s3() -> Generator[dict[str, AsyncMock], None, None]:
    with (
        patch("app.s3.S3Service.upload_file", new_callable=AsyncMock) as mock_upload,
        patch("app.s3.S3Service.delete_file", new_callable=AsyncMock) as mock_delete,
        patch("app.s3.S3Service.generate_download_url") as mock_url,
    ):
        mock_upload.return_value = "projects/1/documents/mock_doc.pdf"
        mock_delete.return_value = None
        mock_url.return_value = "https://mocked-s3-presigned-url.com/download"
        yield {"upload": mock_upload, "delete": mock_delete, "url": mock_url}


# User fixtures


@pytest_asyncio.fixture
async def test_owner(db_session: AsyncSession) -> User:
    owner = User(
        login="owner_user_test",
        hashed_password=get_password_hash("StrongPassword123!"),
    )
    db_session.add(owner)
    await db_session.flush()
    return owner


@pytest_asyncio.fixture
async def test_participant(db_session: AsyncSession) -> User:
    participant = User(
        login="participant_user_test",
        hashed_password=get_password_hash("StrongPassword123!"),
    )
    db_session.add(participant)
    await db_session.flush()
    return participant


@pytest_asyncio.fixture
async def test_other_user(db_session: AsyncSession) -> User:
    other = User(
        login="unrelated_user_test",
        hashed_password=get_password_hash("StrongPassword123!"),
    )
    db_session.add(other)
    await db_session.flush()
    return other


@pytest_asyncio.fixture
async def other_user(test_other_user: User) -> User:
    return test_other_user


# Auth header fixtures - sync, just build a dict


@pytest.fixture
def owner_headers(test_owner: User) -> dict[str, str]:
    token = create_access_token(user_id=test_owner.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def participant_headers(test_participant: User) -> dict[str, str]:
    token = create_access_token(user_id=test_participant.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_headers(test_other_user: User) -> dict[str, str]:
    token = create_access_token(user_id=test_other_user.id)
    return {"Authorization": f"Bearer {token}"}
