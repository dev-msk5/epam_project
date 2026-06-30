"""
Handles user authentication business logic, only DB operations and security checks
Responsibilities:
- Register new users (validate uniqueness, hash password, persist to DB)
- Authenticate existing users (verify credentials, return user for JWT issuance)
"""

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security import get_password_hash, verify_password

# Initialize app logger
logger = logging.getLogger("app_logger")


async def register_user(db: AsyncSession, login: str, password: str) -> User:
    """Register a user and raise HTTPException when the login is taken"""
    logger.info(f"Attempting to register new user with login: '{login}'")
    existing = await db.execute(select(User).where(User.login == login))
    if existing.scalar_one_or_none():
        logger.warning(f"Registration failed: Login '{login}' is already taken")
        # 409 conflict, login already exists
        raise HTTPException(status_code=409, detail="Login already taken")
    hashed_password = get_password_hash(password)
    new_user = User(login=login, hashed_password=hashed_password)
    try:
        db.add(new_user)
        await db.commit()
    except IntegrityError:  # If two requests race on the same login
        await db.rollback()
        logger.warning(
            f"Registration race condition: Login '{login}' taken during commit"
        )
        raise HTTPException(status_code=409, detail="Login already taken")
    await db.refresh(new_user)
    logger.info(f"User '{login}' successfully registered with ID {new_user.id}")
    return new_user


async def authenticate_user(db: AsyncSession, login: str, password: str) -> User:
    """Authenticate a user or raise HTTPException if auth fails"""
    logger.info(f"Attempting authentication for user: '{login}'")
    result = await db.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        logger.warning(f"Authentication failed: Invalid credentials for user '{login}'")
        raise HTTPException(
            status_code=401,  # Unauthorized
            detail="Invalid login or password",
        )
    logger.info(f"User '{login}' successfully authenticated (ID: {user.id})")
    return user
