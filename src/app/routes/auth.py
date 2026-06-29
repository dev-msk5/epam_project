from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.pydantic_schemas.token import TokenOut
from app.pydantic_schemas.user import UserCreate, UserLogin, UserOut
from app.security import create_access_token
from app.services.auth import authenticate_user, register_user

""""
  - POST /auth                          (Create user/register)
  - POST /login                         (Login into service)
"""

router = APIRouter()


@router.post("/auth", status_code=201, response_model=UserOut)  # Created
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    """Register a new user and return the created user data"""
    # user registering from service, returns UserOut
    user = await register_user(session, user_data.login, user_data.password)
    return user


@router.post("/login", status_code=200, response_model=TokenOut)  # OK
async def login(credentials: UserLogin, session: AsyncSession = Depends(get_session)):
    """Authenticate a user and return an access token"""
    user = await authenticate_user(session, credentials.login, credentials.password)
    token = create_access_token(user.id)
    return TokenOut(access_token=token)
