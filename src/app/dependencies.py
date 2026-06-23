# src/app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jwt.exceptions import InvalidTokenError
import jwt

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.config import settings

# Tells FastAPI where the login endpoint is
# Also adds the Authorize button in /docs UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# ─────────────────────────────────────────
#  Database Session
# ─────────────────────────────────────────


async def get_db() -> AsyncSession:
    """
    Provides a fresh DB session for every request.
    Automatically closes it when the request is done.
    """
    async with AsyncSessionLocal() as session:
        yield session          # ← gives session to route
        # ← closes after route finishes

# ─────────────────────────────────────────
# Current User
# ─────────────────────────────────────────


async def get_current_user(
    token: str = Depends(oauth2_scheme),   # ← reads JWT from header
    db: AsyncSession = Depends(get_db)     # ← uses get_db dependency
) -> User:
    """
    Decodes the JWT token and returns the logged-in user.
    Raises 401 if token is missing, expired, or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401)

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists"
        )
    return user

# ─────────────────────────────────────────
# Owner Check
# ─────────────────────────────────────────
# Optional helper used in project routes


def require_owner(project_owner_id: int, current_user: User):
    """
    Raises 403 if current user is not the project owner.
    Used in DELETE /project and POST /project/invite
    """
    if project_owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can perform this action"
        )
