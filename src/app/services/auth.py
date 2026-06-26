# register, login, hash/verify password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from fastapi import HTTPException


from app.security import get_password_hash, verify_password
from app.models.user import User


async def register_user(db: AsyncSession, login: str, password: str) -> User:
    existing = await db.execute(select(User).where(User.login == login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Login already taken")
    hashed_password = get_password_hash(password)
    new_user = User(login=login, hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def authenticate_user(db: AsyncSession, login: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
