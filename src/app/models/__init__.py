from app.db.base import Base  # Import Base here
from app.models.access import Access
from app.models.document import Document
from app.models.project import Project
from app.models.user import User

# This makes all models available for Alembic auto-migration discovery
__all__ = ["Base", "User", "Project", "Document", "Access"]
