from contextlib import asynccontextmanager

from argon2 import hash_password
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, delete, select

from app.routes import auth, projects, documents
from app.db.session import init_db, get_session, engine
from app.models.user import User
from app.models.project import Project
from app.models.document import Document


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for the application lifespan
    """
    # start
    await init_db()

    async with AsyncSession(engine) as session:
        # Check if test_user already exists
        result = await session.execute(
            select(User).where(User.login == "test_user")
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            new_user = existing_user
        else:
            new_user = User(
                login="test_user",
                hashed_password=hash_password(
                    # expects bytes , then decode to str for database storage
                    "test_password".encode()).decode()
            )
            session.add(new_user)
            await session.flush()

        # Check if Test Project already exists for this user
        result = await session.execute(
            select(Project).where(
                (Project.name == "Test Project") &
                (Project.owner_id == new_user.id)
            )
        )
        existing_project = result.scalar_one_or_none()

        if existing_project:
            new_project = existing_project
        else:
            new_project = Project(
                name="Test Project",
                owner_id=new_user.id,
                description="This is a test project."
            )
            session.add(new_project)
            await session.flush()

        # Check if Test Document already exists for this project
        result = await session.execute(
            select(Document).where(
                (Document.name == "Test Document") &
                (Document.project_id == new_project.id)
            )
        )
        existing_document = result.scalar_one_or_none()

        if not existing_document:
            new_document = Document(
                name="Test Document",
                project_id=new_project.id,
                url="http://example.com/test_document",
                created_at=text("CURRENT_TIMESTAMP"),
                updated_at=text("CURRENT_TIMESTAMP"),
                owner_id=new_user.id,
            )
            session.add(new_document)

        await session.commit()

    # APP runs
    yield

    # cleanup after shutdown
    async with AsyncSession(engine) as session:
        await session.execute(delete(Document))
        await session.execute(delete(Project))
        await session.execute(delete(User))
        await session.commit()


app = FastAPI(title="Project Dashboard", lifespan=lifespan)

# Routing from router/ folder to app
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)


@app.get("/")
async def root():
    """Root endpoint for the Project Dashboard API"""
    return {"message": "Welcome to the Project Dashboard API"}


@app.get("/health")
async def health():
    """Health check endpoint for the Project Dashboard API"""
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_session)):
    """Health check endpoint for the database connection"""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
