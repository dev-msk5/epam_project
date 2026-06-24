# src/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, delete

from app.routes import auth, projects, documents
from app.db.session import init_db, get_session, engine
from app.models.user import User
from app.models.project import Project
from app.models.document import Document


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────
    await init_db()

    async with AsyncSession(engine) as session:
        new_user = User(
            id=1,
            login="test_user",
            hashed_password="test_password")
        session.add(new_user)
        await session.flush()                        # flush to get new_user.id assigned

        new_project = Project(
            id=1,
            name="Test Project",
            owner_id=new_user.id,            # use owner_id not owner
            description="This is a test project."
        )
        session.add(new_project)
        # flush to get new_project.id assigned
        await session.flush()

        new_document = Document(
            id=1,
            name="Test Document",
            project_id=new_project.id,               # now new_project.id exists
            url="http://example.com/test_document",
            created_at=text("CURRENT_TIMESTAMP"),
            updated_at=text("CURRENT_TIMESTAMP")
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

# Routing from other folders to app
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Project Dashboard API"}


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.get("/healthz/db")
async def health_db(db: AsyncSession = Depends(get_session)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
