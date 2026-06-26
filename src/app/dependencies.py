# src/app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.db.session import get_session
from app.models.user import User
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Decodes the JWT token and returns the logged-in user.
    Raises 401 if token is missing, expired, or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists"
        )
    return user


def require_owner(project_owner_id: int, current_user: User) -> None:
    """
    Raises 403 if current user is not the project owner.
    Used in DELETE /project and POST /project/invite.
    """
    if project_owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can perform this action"
        )
