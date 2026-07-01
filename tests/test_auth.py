# Integration tests for POST /auth, POST /login, and token behaviour on GET /projects
#
# test_register - covered cases:
#   valid registration returns 201 or 200
#   password is hashed in DB, never stored plaintext
#   hashed password verifies correctly
#   passwords don't match returns 422 with message
#   login shorter than 8 chars returns 422
#   password shorter than 8 chars returns 422
#   duplicate login returns 409
#   missing login field returns 422
#   missing password field returns 422
# missing repeat_password field returns 422
#
# test_login - covered cases:
#   valid credentials return 200 + access_token + token_type bearer
#   token subject (sub) matches authenticated user id
#   wrong password returns 401
#   non-existent login returns 401
#   missing password field returns 422
#   missing login field returns 422
#
# test_token_behavior - covered cases:
#   valid token is accepted on a protected route
#   expired token returns 401
#   malformed token returns 401
#   missing token returns 401
#   tampered token (wrong signature) returns 401
#   wrong auth scheme (Token instead of Bearer) returns 401

from datetime import datetime, timedelta, timezone

import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.user import User
from app.security import verify_password

# registration


async def test_register_user_success(client: AsyncClient, db_session: AsyncSession):
    payload = {
        "login": "new_register_user",
        "password": "SecurePassword123!",
        "repeat_password": "SecurePassword123!",
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code in [200, 201], "registration should succeed"

    stmt = select(User).where(User.login == "new_register_user")
    db_user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert db_user is not None, "registered user should be stored"
    assert db_user.hashed_password != "SecurePassword123!", (
        "password must not be stored in plaintext"
    )
    assert (
        verify_password(
            "SecurePassword123!",
            db_user.hashed_password,
        )
        is True
    ), "stored hash should verify the original password"


async def test_register_returns_user_data(client: AsyncClient):
    payload = {
        "login": "data_check_user",
        "password": "SecurePassword123!",
        "repeat_password": "SecurePassword123!",
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code in [200, 201], "registration should succeed"

    data = response.json()
    assert data["login"] == "data_check_user", (
        "response should return the created login"
    )
    assert "password" not in data, "password must not appear in response"
    assert "hashed_password" not in data, "hashed password must not appear in response"


async def test_register_password_mismatch(client: AsyncClient):
    payload = {
        "login": "different_passwords",
        "password": "SecurePassword123!",
        "repeat_password": "WrongPassword456!",
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, "password mismatch should fail"

    data = response.json()
    assert "Passwords do not match" in str(data["detail"]), (
        "response should explain the password mismatch"
    )


async def test_register_short_login(client: AsyncClient):
    payload = {
        "login": "short",
        "password": "SecurePassword123!",
        "repeat_password": "SecurePassword123!",
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, "short login should fail"


async def test_register_short_password(client: AsyncClient):
    payload = {
        "login": "validlogin_user",
        "password": "short",
        "repeat_password": "short",
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, "short password should fail"


async def test_register_duplicate_login(client: AsyncClient, test_owner: User):
    # test_owner already has login "owner_user_test"
    payload = {
        "login": "owner_user_test",
        "password": "StrongPassword123!",
        "repeat_password": "StrongPassword123!",
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code == 409, "duplicate login should fail"


async def test_register_missing_login(client: AsyncClient):
    payload = {
        "password": "SecurePassword123!",
        "repeat_password": "SecurePassword123!",
    }
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, "missing login should fail"


async def test_register_missing_password(client: AsyncClient):
    payload = {"login": "some_valid_user", "repeat_password": "SecurePassword123!"}
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, "missing password should fail"


async def test_register_missing_repeat_password(client: AsyncClient):
    payload = {"login": "another_valid_user", "password": "SecurePassword123!"}
    response = await client.post("/auth", json=payload)
    assert response.status_code == 422, "missing repeat password should fail"


# login


async def test_login_success(client: AsyncClient, test_owner: User):
    payload = {"login": "owner_user_test", "password": "StrongPassword123!"}
    response = await client.post("/login", json=payload)
    assert response.status_code == 200, "login should succeed"

    data = response.json()
    assert "access_token" in data, "login should return access token"
    assert data["token_type"] == "bearer", "token type should be bearer"
    assert len(data["access_token"]) > 0, "access token should not be empty"


async def test_login_token_contains_user_id(client: AsyncClient, test_owner: User):
    payload = {"login": "owner_user_test", "password": "StrongPassword123!"}
    response = await client.post("/login", json=payload)
    assert response.status_code == 200, "login should succeed"

    token = response.json()["access_token"]
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["sub"] == str(test_owner.id), (
        "token subject should match the owner id"
    )


async def test_login_wrong_password(client: AsyncClient, test_owner: User):
    payload = {"login": "owner_user_test", "password": "wrongpassword"}
    response = await client.post("/login", json=payload)
    assert response.status_code == 401, "wrong password should fail"


async def test_login_nonexistent_user(client: AsyncClient):
    payload = {"login": "ghost_user_xyz", "password": "SomePassword1!"}
    response = await client.post("/login", json=payload)
    assert response.status_code == 401, "unknown login should fail"


async def test_login_missing_password(client: AsyncClient):
    payload = {"login": "owner_user_test"}
    response = await client.post("/login", json=payload)
    assert response.status_code == 422, "missing password should fail"


async def test_login_missing_login(client: AsyncClient):
    payload = {"password": "StrongPassword123!"}
    response = await client.post("/login", json=payload)
    assert response.status_code == 422, "missing login should fail"


# token behavior on protected routes


async def test_valid_token_accepted_on_protected_route(
    client: AsyncClient, owner_headers: dict
):
    response = await client.get("/projects", headers=owner_headers)
    assert response.status_code == 200, "valid token should be accepted"


async def test_missing_token_returns_401(client: AsyncClient):
    response = await client.get("/projects")
    assert response.status_code == 401, "missing token should fail"


async def test_malformed_token_returns_401(client: AsyncClient):
    headers = {"Authorization": "Bearer this.is.garbage"}
    response = await client.get("/projects", headers=headers)
    assert response.status_code == 401, "malformed token should fail"


async def test_expired_token_returns_401(client: AsyncClient):
    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
    }
    token = jwt.encode(
        expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/projects", headers=headers)
    assert response.status_code == 401, "expired token should fail"


async def test_tampered_token_returns_401(client: AsyncClient, test_owner: User):
    token = jwt.encode(
        {
            "sub": str(test_owner.id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "super-test-secret-key-not-for-production-use-only-32bytes",
        algorithm=settings.ALGORITHM,
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/projects", headers=headers)
    assert response.status_code == 401, "tampered token should fail"


async def test_wrong_scheme_returns_401(client: AsyncClient, owner_headers: dict):
    # Send token with "Token" prefix instead of "Bearer"
    raw_token = owner_headers["Authorization"].split(" ")[1]
    headers = {"Authorization": f"Token {raw_token}"}
    response = await client.get("/projects", headers=headers)
    assert response.status_code == 401, "wrong auth scheme should fail"
