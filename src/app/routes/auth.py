from fastapi import APIRouter

#   - POST /auth                          (Create user/register)
#   - POST /login                         (Login into service)

router = APIRouter()


@router.post("/auth")
async def auth(login: str, password: str, repeat_password: str):
    return {"message": f"User {login} created successfully"}


@router.post("/login")
async def login(login: str, password: str):
    return {"message": f"User {login} logged in"}
