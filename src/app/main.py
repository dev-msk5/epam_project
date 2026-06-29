from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, get_session, init_db
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.routes import auth, documents, projects
from app.security import get_password_hash


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for the application lifespan"""
    await init_db()

    async with AsyncSession(engine) as session:
        # Seed: test_user
        result = await session.execute(select(User).where(User.login == "test_user"))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            new_user = existing_user
        else:
            new_user = User(
                login="test_user",
                hashed_password=get_password_hash("test_password"),
            )
            session.add(new_user)
            await session.flush()

        # Seed: Test Project
        result = await session.execute(
            select(Project).where(
                (Project.name == "Test Project") & (
                    Project.owner_id == new_user.id)
            )
        )
        existing_project = result.scalar_one_or_none()

        if existing_project:
            new_project = existing_project
        else:
            new_project = Project(
                name="Test Project",
                owner_id=new_user.id,
                description="This is a test project.",
            )
            session.add(new_project)
            await session.flush()

        # Seed: Test Document
        result = await session.execute(
            select(Document).where(
                (Document.name == "Test Document")
                & (Document.project_id == new_project.id)
            )
        )
        existing_document = result.scalar_one_or_none()

        if not existing_document:
            new_document = Document(
                name="Test Document",
                project_id=new_project.id,
                url="http://example.com/test_document",
                owner_id=new_user.id,
            )
            session.add(new_document)

        await session.commit()

    # App runs
    yield


app = FastAPI(title="Project Dashboard", lifespan=lifespan)

# Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)

# Frontend after API routers, serving static files from the /frontend directory
app.mount("/", StaticFiles(directory="src/frontend", html=True), name="static")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_session)):
    """Database connectivity check."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
