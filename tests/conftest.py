import asyncio  # for testing async code across multiple backends
import gc
import os
import socket
from typing import AsyncGenerator, Generator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.base import Base
from app.db.session import get_session
from app.config import settings
from app.security import create_access_token, get_password_hash


from app.models.user import User
from app.models.project import Project
from app.models.document import Document
from app.models.access import Access


# Parse and resolve Database URL
DATABASE_URL = settings.DATABASE_URL
if "postgresql+asyncpg://" in DATABASE_URL:
    base_url, db_name = DATABASE_URL.rsplit("/", 1)
    if db_name == "test_db" or db_name.endswith("_test") or db_name.endswith("test"):
        TEST_DATABASE_URL = DATABASE_URL
    else:
        TEST_DATABASE_URL = f"{base_url}/{db_name}_test"

    # Smart Host Resolution (Windows local vs Docker)
    if "@db:" in TEST_DATABASE_URL or "@db/" in TEST_DATABASE_URL:
        try:
            socket.getaddrinfo("db", 5432)
        except socket.gaierror:
            TEST_DATABASE_URL = TEST_DATABASE_URL.replace(
                "@db:", "@localhost:").replace("@db/", "@localhost/")
else:
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DATABASE_URL)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide a single, stable event loop for the entire test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a session-scoped async engine with NullPool"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool  # Prevents connections from being pooled across closed loops
    )
    yield engine
    # Explicitly clean up all engine resources on teardown
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def setup_db(test_engine):
    """Create all tables once per session and drop them at the end"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transaction-isolated database session for each test. 
    Rolls back any changes after the test completes
    """
    async with test_engine.connect() as connection:
        await connection.begin()

        # bind the factory to the connection, not the engine
        # this is the only line that changed from the broken version
        session_factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with session_factory() as session:
            yield session

        await connection.rollback()


@pytest.fixture(autouse=True)
def override_dependencies(db_session: AsyncSession):
    """Override the FastAPI get_session dependency with our rollback-enabled session"""
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
async def cleanup_event_loop_barrier():
    """Ensure background S3 and DB connections are collected before exit"""
    yield
    gc.collect()
    await asyncio.sleep(0.1)


@pytest.fixture
def mock_s3() -> Generator[dict[str, AsyncMock], None, None]:
    """Mock AWS S3 calls so tests do not need internet or credentials."""
    with (
        patch("app.s3.S3Service.upload_file", new_callable=AsyncMock) as mock_upload,
        patch("app.s3.S3Service.delete_file", new_callable=AsyncMock) as mock_delete,
        patch("app.s3.S3Service.generate_download_url") as mock_url,
    ):

        mock_upload.return_value = "projects/1/documents/mock_doc.pdf"
        mock_delete.return_value = None
        mock_url.return_value = "https://mocked-s3-presigned-url.com/download"

        yield {
            "upload": mock_upload,
            "delete": mock_delete,
            "url": mock_url
        }


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous client for making test API requests"""
    # Use ASGITransport to pass the FastAPI app in httpx >= 0.28.0
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


#  Shared User Fixtures

@pytest.fixture
async def test_owner(db_session: AsyncSession) -> User:
    """Create a default project owner user."""
    owner = User(
        login="owner_user_test",
        hashed_password=get_password_hash("StrongPassword123!")
    )
    db_session.add(owner)
    await db_session.flush()
    return owner


@pytest.fixture
async def test_participant(db_session: AsyncSession) -> User:
    """Create a default participant user"""
    participant = User(
        login="participant_user_test",
        hashed_password=get_password_hash("StrongPassword123!")
    )
    db_session.add(participant)
    await db_session.flush()
    return participant


@pytest.fixture
async def test_other_user(db_session: AsyncSession) -> User:
    """Create an unrelated user with no shared project access"""
    other = User(
        login="unrelated_user_test",
        hashed_password=get_password_hash("StrongPassword123!")
    )
    db_session.add(other)
    await db_session.flush()
    return other


# alias so tests can request either name
@pytest.fixture
async def other_user(test_other_user: User) -> User:
    return test_other_user


#  Authentication Header Fixtures

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
