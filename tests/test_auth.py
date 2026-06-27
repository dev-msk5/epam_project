# register, login, bad password, duplicate user
from app.security import verify_password
from app.models.user import User
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient


class test_register():
    pass
#  valid registration returns 201 + user data
#  passwords don't match returns 422
#  login shorter than 8 chars returns 422
#  password shorter than 8 chars returns 422
# duplicate login returns 409
#  missing fields returns 422


class test_login():
    pass
#  valid credentials returns 200 + access_token + token_type="bearer"
#  wrong password returns 401
#  non-existent login returns 401
#  missing password returns 422
#  missing login returns 422


class test_token_expiry():
    pass
#  valid token is accepted on protected route
#  expired token returns 401
#  malformed token returns 401
#  missing token returns 401
#  tampered token (wrong signature) returns 401


async def test_register_user_success(client: AsyncClient, db_session: AsyncSession):
    """Verify registration succeeds and password safety properties are maintained"""
    payload = {
        "login": "new_register_user",  # >= 8 characters
        "password": "SecurePassword123!",  # >= 8 characters
        "repeat_password": "SecurePassword123!"
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code in [
        200, 201], " Registration should succeed with 200 or 201"

    # Assert DB registration & password safety properties
    stmt = select(User).where(User.login == "new_register_user")
    db_user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert db_user is not None, "User should be created in the database"
    # Never store raw text
    assert db_user.hashed_password != "SecurePassword123!", "Hashed password should not match the plain text password"
    assert verify_password("SecurePassword123!",
                           db_user.hashed_password) is True, "Password verification should succeed with the correct password"


async def test_register_user_password_mismatch(client: AsyncClient):
    """Verify custom passwords_match validator rejects mismatches with 422."""
    payload = {
        "login": "different_passwords",
        "password": "SecurePassword123!",
        "repeat_password": "WrongPassword456!"
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, " Registration should fail with 422 for password mismatch"

    # Check that custom validation error message is delivered
    data = response.json()
    assert "Passwords do not match" in str(
        data["detail"]), " Custom validator should indicate password mismatch"


async def test_register_user_short_login(client: AsyncClient):
    """Verify schema min_length=8 constraints for logins are enforced (422)"""
    payload = {
        "login": "short",  # Under 8 characters
        "password": "SecurePassword123!",
        "repeat_password": "SecurePassword123!"
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, " Registration should fail with 422 for short login"


async def test_login_success(client: AsyncClient, test_owner: User):
    """Verify active bearer token is generated with correct fields (TokenOut schema)"""
    payload = {
        "login": "owner_user_test",
        "password": "StrongPassword123!"
    }
    response = await client.post("/login", json=payload)
    assert response.status_code == 200, "Login should succeed with 200"
    data = response.json()
    assert data["access_token"] is not None, "Access token should be present in the response"
    assert data["token_type"] == "bearer", "Token type should be 'bearer' for JWT authentication"


async def test_login_invalid_password(client: AsyncClient, test_owner: User):
    """Verify authentication fails when credentials are bad"""
    payload = {
        "login": "owner_user_test",
        "password": "wrongpassword"
    }
    response = await client.post("/login", json=payload)
    assert response.status_code == 401, "Login should fail with 401 for invalid credentials"


async def test_jwt_protected_route_requires_token(client: AsyncClient):
    """Verify secure endpoints reject unauthenticated requests with 401"""
    response = await client.get("/projects")
    assert response.status_code == 401, "Unauthenticated requests should be rejected with 401"
