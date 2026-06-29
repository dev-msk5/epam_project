# Unit tests for security.py and dependencies.py
#
# security.py covered cases:
#   get_password_hash        - returns a non-plaintext string
#   verify_password          - correct password passes, wrong password fails
#   verify_and_update_password - bcrypt hash triggers upgrade to argon2
#   create_access_token      - token is a non-empty string, decodes to correct user_id
#   decode_access_token      - valid token returns user_id
#                            - expired token raises 401 "Token has expired"
#                            - tampered signature raises 401
#                            - malformed token string raises 401
#                            - missing "sub" field in payload raises 401
#                            - sub is non-numeric raises 401
#
# dependencies.py covered cases:
#   get_current_user         - valid token + existing user returns user object
#                            - valid token but user deleted from DB raises 401
#                            - expired token raises 401
#                            - invalid token raises 401
#   require_owner            - matching user_id passes silently
#                            - different user_id raises 403

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.security import (
    get_password_hash,
    verify_password,
    verify_and_update_password,
    create_access_token,
    decode_access_token,
)
from app.dependencies import get_current_user, require_owner
from app.config import settings


# get_password_hash

def test_hash_is_not_plaintext():
    hashed = get_password_hash("MySecret123!")
    assert hashed != "MySecret123!", " Hashed password should not match the plain text password"


def test_hash_is_string():
    hashed = get_password_hash("MySecret123!")
    assert isinstance(hashed, str) and len(
        hashed) > 0, " Hashed password should be a non-empty string"


# verify_password

def test_verify_password_correct():
    hashed = get_password_hash("CorrectHorse99!")
    assert verify_password(
        "CorrectHorse99!", hashed) is True, " Password verification should succeed with the correct password"


def test_verify_password_wrong():
    hashed = get_password_hash("CorrectHorse99!")
    assert verify_password(
        "WrongPassword!", hashed) is False, " Password verification should fail with the wrong password"


def test_verify_password_empty_string_fails():
    hashed = get_password_hash("SomePassword1!")
    assert verify_password(
        "", hashed) is False, " Password verification should fail with an empty password"


# verify_and_update_password

def test_verify_and_update_bcrypt_triggers_upgrade():
    # Produce a bcrypt hash directly so the upgrade path is exercised
    from pwdlib import PasswordHash
    from pwdlib.hashers.bcrypt import BcryptHasher

    bcrypt_only = PasswordHash((BcryptHasher(),))
    bcrypt_hash = bcrypt_only.hash("OldBcryptPass1!")

    valid, new_hash = verify_and_update_password(
        "OldBcryptPass1!", bcrypt_hash)

    assert valid is True, "Password verification should succeed with the correct password"
    # When the primary hasher (Argon2) is stronger, pwdlib returns a new hash
    assert new_hash is not None, "A bcrypt hash should trigger an upgrade to Argon2"
    assert new_hash != bcrypt_hash, "The new hash should be different from the old bcrypt hash"


def test_verify_and_update_argon2_no_upgrade_needed():
    argon2_hash = get_password_hash("AlreadyArgon2!")

    valid, new_hash = verify_and_update_password("AlreadyArgon2!", argon2_hash)

    assert valid is True, "Password verification should succeed with the correct password"
    # Already using the strongest hasher
    assert new_hash is None, "No upgrade needed if already using the strongest hasher"


def test_verify_and_update_wrong_password():
    hashed = get_password_hash("RightPassword1!")

    valid, new_hash = verify_and_update_password("WrongPassword1!", hashed)

    assert valid is False, "Password verification should fail with the wrong password"


# create_access_token

def test_create_access_token_returns_string():
    token = create_access_token(user_id=42)
    assert isinstance(token, str) and len(
        token) > 0, "Access token should be a non-empty string"


def test_create_access_token_contains_correct_user_id():
    token = create_access_token(user_id=7)
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )
    assert payload["sub"] == "7", "Decoded token payload should contain the correct user_id in 'sub'"


def test_create_access_token_has_expiry():
    token = create_access_token(user_id=1)
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )
    assert "exp" in payload, "Decoded token payload should contain an expiry time"


#  decode_access_token

def test_decode_valid_token_returns_user_id():
    token = create_access_token(user_id=99)
    result = decode_access_token(token)
    assert result == 99, " Decoded token should return the correct user_id"


def test_decode_expired_token_raises_401():
    expired_payload = {
        "sub": "5",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1)
    }
    token = jwt.encode(
        expired_payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401, " Expired token should raise a 401 error"
    assert "expired" in exc.value.detail.lower(
    ), " Error message should indicate that the token has expired"


def test_decode_tampered_signature_raises_401():
    token = create_access_token(user_id=3)
    # Flip the last few chars to break the signature
    tampered = token[:-6] + "aaaaaa"
    with pytest.raises(HTTPException) as exc:
        decode_access_token(tampered)
    assert exc.value.status_code == 401, "Tampered token should raise a 401 error"


def test_decode_malformed_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_access_token("this.is.not.a.jwt")
    assert exc.value.status_code == 401, "Malformed token should raise a 401 error"


def test_decode_missing_sub_raises_401():
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        # no "sub"
    }
    token = jwt.encode(payload, settings.SECRET_KEY,
                       algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401, "Token with missing 'sub' should raise a 401 error"
    assert "credentials" in exc.value.detail.lower(
    ), "Error message should indicate missing credentials"


def test_decode_non_numeric_sub_raises_401():
    payload = {
        "sub": "not-a-number",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }
    token = jwt.encode(payload, settings.SECRET_KEY,
                       algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401, "Token with non-numeric 'sub' should raise a 401 error"


def test_decode_wrong_secret_raises_401():
    payload = {
        "sub": "10",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }
    token = jwt.encode(payload, "super-test-secret-key-not-for-production-use-only-32bytes",
                       algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401, "Token with wrong secret should raise a 401 error"


#  get_current_user

@pytest.mark.anyio
async def test_get_current_user_returns_user_for_valid_token():
    token = create_access_token(user_id=1)

    mock_user = MagicMock()
    mock_user.id = 1

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_user)

    result = await get_current_user(token=token, db=mock_db)

    assert result is mock_user, " get_current_user should return the user object for a valid token"
    mock_db.get.assert_called_once()


@pytest.mark.anyio
async def test_get_current_user_deleted_user_raises_401():
    # Token is valid but the user no longer exists in the DB
    token = create_access_token(user_id=999)

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=mock_db)

    assert exc.value.status_code == 401, "Deleted user should raise a 401 error"
    assert "no longer exists" in exc.value.detail.lower(
    ), "Error message should indicate that the user no longer exists"


@pytest.mark.anyio
async def test_get_current_user_expired_token_raises_401():
    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1)
    }
    token = jwt.encode(
        expired_payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=mock_db)

    assert exc.value.status_code == 401, "Expired token should raise a 401 error"
    assert "expired" in exc.value.detail.lower(
    ), "Error message should indicate that the token has expired"


@pytest.mark.anyio
async def test_get_current_user_invalid_token_raises_401():
    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await get_current_user(token="garbage.token.value", db=mock_db)

    assert exc.value.status_code == 401, "Invalid token should raise a 401 error"


@pytest.mark.anyio
async def test_get_current_user_missing_sub_raises_401():
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }
    token = jwt.encode(payload, settings.SECRET_KEY,
                       algorithm=settings.ALGORITHM)

    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=mock_db)

    assert exc.value.status_code == 401, "Token with missing 'sub' should raise a 401 error"
    assert "invalid token payload" in exc.value.detail.lower(
    ), "Error message should indicate invalid token payload"


# require_owner

def test_require_owner_passes_for_matching_user():
    mock_user = MagicMock()
    mock_user.id = 5
    # should not raise
    require_owner(project_owner_id=5, current_user=mock_user)


def test_require_owner_raises_403_for_wrong_user():
    mock_user = MagicMock()
    mock_user.id = 8

    with pytest.raises(HTTPException) as exc:
        require_owner(project_owner_id=5, current_user=mock_user)

    assert exc.value.status_code == 403, "require_owner should raise 403 for a user that is not the owner"
    assert "owner" in exc.value.detail.lower(
    ), " Error message should indicate that the user is not the owner"


def test_require_owner_raises_403_for_participant(
    test_participant, participant_headers
):
    # Simulate a participant user object trying to act as owner
    mock_participant = MagicMock()
    mock_participant.id = 99

    with pytest.raises(HTTPException) as exc:
        require_owner(project_owner_id=1, current_user=mock_participant)

    assert exc.value.status_code == 403, " require_owner should raise 403 for a participant user that is not the owner"
