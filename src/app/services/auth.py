# register, login, hash/verify password
from app.services.auth import get_password_hash, verify_password
from app.models.user import User


from sqlalchemy.ext.asyncio import AsyncSession


async def register_user(db: AsyncSession, username: str, password: str) -> User:
    hashed_password = get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    pass
