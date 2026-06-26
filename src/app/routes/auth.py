from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.pydantic_schemas.user import UserCreate, UserLogin
from src.app.db.session import get_session
from app.db.session import get_session

#   - POST /auth                          (Create user/register)
#   - POST /login                         (Login into service)

router = APIRouter()


@router.post("/auth", status_code=201)  # Created
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    # result = await auth_service.register(user_data, session)
    return None  #

# TODO response_model=UserOut, status_code=201

# response_model=TokenOut ?


@router.post("/login", status_code=200)  # OK
async def login(credentials: UserLogin,
                session: AsyncSession = Depends(get_session)):
    # await auth_service.login(credentials, session)
    return None
