"""JWT primitives. Routes should use dependencies/access.py to authenticate requests."""

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"  # Fixed by the server; never trust a token's requested algorithm.
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Call before storing a password; never store or log the plaintext value."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Compare a login password to the stored Argon2 hash."""
    return password_hash.verify(password, hashed_password)


def _create_token(user_id: int, token_type: str, lifetime: timedelta, version: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": token_type,
            "ver": version,
            "iat": now,
            "exp": now + lifetime,
            "jti": uuid4().hex,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def create_access_token(user_id: int, version: int = 0) -> str:
    """Short-lived bearer token. Do not put passwords or private data in JWT payloads."""
    return _create_token(
        user_id, "access", timedelta(minutes=get_settings().access_token_expire_minutes), version
    )


def create_refresh_token(user_id: int, version: int = 0) -> str:
    """Use services/auth.py to also persist its revocable session record."""
    return _create_token(
        user_id, "refresh", timedelta(days=get_settings().refresh_token_expire_days), version
    )


def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> dict:
    """Validate signature, expiry, issuer, audience and type; raises InvalidTokenError."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "exp", "iat", "jti", "type", "ver", "iss", "aud"]},
    )
    subject = payload["sub"]
    if (
        payload["type"] != expected_type
        or not isinstance(subject, str)
        or len(subject) > 19
        or not subject.isascii()
        or not subject.isdigit()
        or not 0 < int(subject) <= 2**63 - 1
        or type(payload["ver"]) is not int
        or not isinstance(payload["jti"], str)
    ):
        raise jwt.InvalidTokenError("Invalid token claims")
    return payload
