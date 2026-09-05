import time

import jwt
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.dependencies.access import unauthorized
from app.models import RefreshSession, User
from app.schemas.contracts import TokenPair


def issue_tokens(db: Session, user: User) -> TokenPair:
    """Stage a refresh session; the caller commits it with the surrounding transaction."""
    refresh = create_refresh_token(user.id, user.token_version)
    claims = decode_token(refresh, "refresh")
    db.add(RefreshSession(jti=claims["jti"], user_id=user.id, expires_at=claims["exp"]))
    return TokenPair(
        access_token=create_access_token(user.id, user.token_version),
        refresh_token=refresh,
    )


def consume_refresh(db: Session, token: str) -> User:
    """Atomic DELETE makes each refresh token single-use, including concurrent requests."""
    try:
        claims = decode_token(token, "refresh")
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    user = db.get(User, int(claims["sub"]))
    if not user or not user.is_active or user.token_version != claims["ver"]:
        raise unauthorized()
    result = db.execute(
        delete(RefreshSession).where(
            RefreshSession.jti == claims["jti"],
            RefreshSession.user_id == user.id,
            RefreshSession.expires_at > int(time.time()),
        )
    )
    if result.rowcount != 1:
        raise unauthorized()
    return user
