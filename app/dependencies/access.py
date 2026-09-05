from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.session import get_db
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def unauthorized() -> HTTPException:
    return HTTPException(
        401, "Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """Add `user: CurrentUser` to any route to require an active authenticated user."""
    try:
        claims = decode_token(token)
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    user = db.get(User, int(claims["sub"]))
    if not user or not user.is_active or user.token_version != claims["ver"]:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_superuser(user: CurrentUser) -> User:
    """Use `admin: AdminUser` on administrative endpoints. Public signup cannot set this flag."""
    if not user.is_superuser:
        raise HTTPException(403, "Administrator access required")
    return user


AdminUser = Annotated[User, Depends(require_superuser)]
