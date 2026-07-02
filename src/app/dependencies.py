from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.access import Access
from app.models.user import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Decodes the JWT token and returns the logged-in user.
    Raises 401 if token is missing, expired, or invalid.
    """
    user_id = decode_access_token(token)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists"
        )
    return user


async def require_owner(
    project_id: int,
    current_user: User,
    db: AsyncSession,
) -> None:
    """
    Raises 403 if current user is not the project owner.
    Used in DELETE /project and POST /project/invite.
    """
    role = await Access.get_role_for_project(db, project_id, current_user.id)
    if role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can perform this action",
        )
