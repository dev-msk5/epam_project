from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import settings

# Initialize Argon2 as the primary hasher and Bcrypt as fallback
pwd_context = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


def get_password_hash(password: str) -> str:
    """Hash password using the primary algorithm (Argon2)"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify standard plain password against a hashed version"""
    return pwd_context.verify(plain, hashed)


def verify_and_update_password(plain: str, hashed: str) -> tuple[bool, str | None]:
    """
    Verify a password and upgrade the hash when a stronger algorithm is needed

    Returns (True, new_hash) if an update is needed, otherwise (True, None)
    """
    return pwd_context.verify_and_update(plain, hashed)


def create_access_token(user_id: int) -> str:
    """Create a timezone-aware JWT access token containing user_id"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> int:
    """
    Decode, verify JWT token and extract user_id
    Raises 401 Unauthorized exceptions if the token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return int(user_id_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
