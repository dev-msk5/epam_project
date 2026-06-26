import jwt
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import settings

# pwdlib password hashing, hence safe storing in DB
# pyjwt for JWT token creation, identification after login

# Hashing
pwd_context = PasswordHash([BcryptHasher()])


def get_password_hash(password: str) -> str:  # hash password using bcrypt
    return pwd_context.hash(password)


# verify password against hashed version
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# JWT Token creation and verification
def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
