from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.db.base import Base
from app.models import User, Project, Document

engine = create_async_engine(settings.DATABASE_URL, echo=True)
# Base.metadata.create_all(engine) not needed here, as we will use Alembic for migrations
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> AsyncSession:
    "Initialize the database and create tables"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    "Get session for database operations"
    async with AsyncSessionLocal() as session:
        yield session
