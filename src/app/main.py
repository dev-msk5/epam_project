from contextlib import asynccontextmanager

# FastAPI imports
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# database configuration
from app.db.session import get_session, init_db

# logger configuration
from app.logging_config import LoggingMiddleware, logger
from app.routes import auth, documents, projects


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for the application lifespan"""
    await init_db()

    logger.info("Application starting...")

    # App runs
    yield


app = FastAPI(title="Project Dashboard", lifespan=lifespan)

# Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)


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
    except Exception:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )


# Frontend after API routers, serving static files from the /frontend directory
app.mount("/", StaticFiles(directory="src/frontend", html=True), name="static")

# Register the logging middleware at the top of the stack
app.add_middleware(LoggingMiddleware)
