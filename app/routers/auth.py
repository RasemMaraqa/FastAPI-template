from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.dependencies.access import CurrentUser, DbSession, unauthorized
from app.models import RefreshSession, User
from app.schemas.contracts import (
    PasswordChange,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserResponse,
)
from app.services.auth import consume_refresh, issue_tokens

router = APIRouter(prefix="/auth", tags=["Authentication"])
# Missing accounts still perform a password hash verification to reduce timing differences.
DUMMY_HASH = hash_password("not-a-real-account-password")


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: UserCreate, db: DbSession):
    user = User(email=str(body.email), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered") from None
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(db: DbSession, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    # OAuth2 calls this field `username`; send the email address in it.
    if len(form.password) > 128:
        raise unauthorized()
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    valid = verify_password(form.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.is_active:
        raise unauthorized()
    tokens = issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: DbSession):
    user = consume_refresh(db, body.refresh_token)
    tokens = issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: DbSession):
    # Revokes this refresh token. Its access token lives until expiry (see logout-all).
    consume_refresh(db, body.refresh_token)
    db.commit()
    return Response(status_code=204)


def revoke_all(db, user):
    # SQL increment avoids lost updates when revocations occur concurrently.
    db.execute(update(User).where(User.id == user.id).values(token_version=User.token_version + 1))
    db.execute(delete(RefreshSession).where(RefreshSession.user_id == user.id))


@router.post("/logout-all", status_code=204)
def logout_all(db: DbSession, user: CurrentUser):
    revoke_all(db, user)
    db.commit()
    return Response(status_code=204)


@router.post("/change-password", status_code=204)
def change_password(body: PasswordChange, db: DbSession, user: CurrentUser):
    if not verify_password(body.current_password, user.password_hash):
        raise unauthorized()
    user.password_hash = hash_password(body.new_password)
    revoke_all(db, user)
    db.commit()
    return Response(status_code=204)
