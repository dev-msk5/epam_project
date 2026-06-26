from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.pydantic_schemas.user import UserCreate, UserLogin, UserOut
from app.pydantic_schemas.token import TokenOut
from app.db.session import get_session
from app.services.auth import register_user, authenticate_user
from app.security import create_access_token

#   - POST /auth                          (Create user/register)
#   - POST /login                         (Login into service)

router = APIRouter()


@router.post("/auth", status_code=201, response_model=UserOut)  # Created
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    # user registering from service, returns UserOut
    user = await register_user(session, user_data.login, user_data.password)
    return user


@router.post("/login", status_code=200, response_model=TokenOut)  # OK
async def login(credentials: UserLogin,
                session: AsyncSession = Depends(get_session)):
    user = await authenticate_user(session, credentials.login, credentials.password)
    token = create_access_token(user.id)
    return TokenOut(access_token=token)
