from fastapi import FastAPI


@app.post("/auth")
async def auth(login: str, password: str, repeat_password: str):
    return {"message": "User created"}


@app.post("/login")
async def login(login: str, password: str):
    return {"message": "User logged in"}
