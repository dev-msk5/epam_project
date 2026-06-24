from fastapi import APIRouter

from app.pydantic_schemas.user import User

#   - POST /auth                          (Create user/register)
#   - POST /login                         (Login into service)

router = APIRouter()


@router.post("/auth", status_code=201)  # Created
async def auth(login: str, password: str, repeat_password: str):
    return {"message": f"User {login} created successfully"}


@router.post("/login", status_code=200)  # OK
async def login(login: str, password: str):
    return {"message": f"User {login} logged in"}
