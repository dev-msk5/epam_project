"""
Handles user authentication business logic, only DB operations and security checks
Responsibilities:
- Register new users (validate uniqueness, hash password, persist to DB)
- Authenticate existing users (verify credentials, return user for JWT issuance)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from fastapi import HTTPException

from app.security import get_password_hash, verify_password
from app.models.user import User


async def register_user(db: AsyncSession, login: str, password: str) -> User:
    """Register a user and raise HTTPException when the login is taken"""
    existing = await db.execute(select(User).where(User.login == login))
    if existing.scalar_one_or_none():
        # 409 conflict, login already exists
        raise HTTPException(status_code=409, detail="Login already taken")
    hashed_password = get_password_hash(password)
    new_user = User(login=login, hashed_password=hashed_password)
    try:
        db.add(new_user)
        await db.commit()
    except IntegrityError:  # If two requests race on the same login.
        await db.rollback()
        raise HTTPException(status_code=409, detail="Login already taken")
    await db.refresh(new_user)
    return new_user


async def authenticate_user(db: AsyncSession, login: str, password: str) -> User:
    """Authenticate a user or raise HTTPException if auth fails"""
    result = await db.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=401,  # Unauthorized
            detail="Invalid login or password"
        )
    return user
