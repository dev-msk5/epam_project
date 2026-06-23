from fastapi import FastAPI
from .routes import auth, projects, documents

from app.models.user import User
from app.models.project import Project
from app.models.document import Document

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from .db.session import init_db,  engine
from contextlib import asynccontextmanager  # look after this

# App entry, router registration, startup events

app = FastAPI(title="Project Dashboard")

# Registering routers — prefix adds to all routes in that router
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Project Dashboard API"}


@asynccontextmanager
async def lifespan(app: FastAPI):  # look after this
    # Startup code
    await init_db()  # Initialize the database and create tables

    async with AsyncSession(engine) as session:
        new_user = User(login="test_user", password="test_password")
        new_project = Project(name="Test Project", owner=new_user.id,
                              description="This is a test project.")
        new_document = Document(name="Test Document", project_id=new_project.id, url="https://example.com/test_document",
                                created_at="2023-01-01 00:00:00", updated_at="2023-01-01 00:00:00")

        session.add(new_user)
        session.add(new_project)
        session.add(new_document)
        await session.commit()

        yield  # This allows the application to run while the context manager is active

        async with AsyncSession(engine) as session:
            await session.execute(delete(Document))
            await session.execute(delete(Project))
            await session.execute(delete(User))
            await session.commit()
