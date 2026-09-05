from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import ALGORITHM, decode_token
from app.dependencies.access import require_superuser
from app.models import User


def headers(pair):
    return {"Authorization": "Bearer " + pair["access_token"]}


def test_registration_and_login(client, account):
    pair = account("Person@example.com")
    response = client.get("/api/v1/users/me", headers=headers(pair))
    assert response.status_code == 200
    assert response.json()["email"] == "person@example.com"
    assert "password_hash" not in response.json()
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "PERSON@example.com",
                "password": "a-strong-password-123",
            },
        ).status_code
        == 409
    )
    for email in ["person@example.com", "missing@example.com"]:
        assert (
            client.post(
                "/api/v1/auth/login",
                data={
                    "username": email,
                    "password": "incorrect",
                },
            ).status_code
            == 401
        )


def test_signup_cannot_grant_admin(client):
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "a@example.com",
                "password": "a-strong-password-123",
                "is_superuser": True,
            },
        ).status_code
        == 422
    )


def test_refresh_rotation_and_logout(client, account):
    first = account()
    body = {"refresh_token": first["refresh_token"]}
    response = client.post("/api/v1/auth/refresh", json=body)
    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json=body).status_code == 401
    assert client.get("/api/v1/users/me", headers=headers(second)).status_code == 200
    body = {"refresh_token": second["refresh_token"]}
    assert client.post("/api/v1/auth/logout", json=body).status_code == 204
    assert client.post("/api/v1/auth/refresh", json=body).status_code == 401
    # A session logout does not revoke already issued access tokens.
    assert client.get("/api/v1/users/me", headers=headers(second)).status_code == 200


@pytest.mark.parametrize("action", ["logout-all", "change-password"])
def test_revoke_all(client, account, action):
    pair = account()
    body = {"current_password": "a-strong-password-123", "new_password": "another-password-123"}
    response = client.post(f"/api/v1/auth/{action}", headers=headers(pair), json=body)
    assert response.status_code == 204
    assert client.get("/api/v1/users/me", headers=headers(pair)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": pair["refresh_token"],
            },
        ).status_code
        == 401
    )
    if action == "change-password":
        for password, status in [(body["current_password"], 401), (body["new_password"], 200)]:
            assert (
                client.post(
                    "/api/v1/auth/login",
                    data={
                        "username": "person@example.com",
                        "password": password,
                    },
                ).status_code
                == status
            )


@pytest.mark.parametrize(
    "claim,value",
    [
        ("sub", "not-an-integer"),
        ("sub", "9" * 100),
        ("type", "refresh"),
        ("aud", "other-api"),
        ("iss", "other-issuer"),
        ("ver", 1),
        ("exp", 1),
        ("jti", None),
    ],
)
def test_bad_claims_rejected(client, account, claim, value):
    pair = account()
    payload = decode_token(pair["access_token"])
    payload[claim] = value
    pair["access_token"] = jwt.encode(
        payload, get_settings().secret_key.get_secret_value(), algorithm=ALGORITHM
    )
    response = client.get("/api/v1/users/me", headers=headers(pair))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_tokens(client, account):
    pair = account()
    for token in ["garbage", pair["refresh_token"], pair["access_token"] + "tampered"]:
        assert (
            client.get(
                "/api/v1/users/me",
                headers={
                    "Authorization": "Bearer " + token,
                },
            ).status_code
            == 401
        )
    assert client.get("/api/v1/users/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": pair["access_token"],
            },
        ).status_code
        == 401
    )
    payload = decode_token(pair["refresh_token"], "refresh")
    payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired = jwt.encode(payload, get_settings().secret_key.get_secret_value(), algorithm=ALGORITHM)
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": expired}).status_code == 401


def test_disabled_user(client, account, db):
    pair = account()
    user = db.get(User, int(decode_token(pair["access_token"])["sub"]))
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/users/me", headers=headers(pair)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": pair["refresh_token"],
            },
        ).status_code
        == 401
    )


def test_ownership_crud_and_pagination(client, account):
    owner = headers(account())
    other = headers(account("other@example.com"))
    response = client.post("/api/v1/items", headers=owner, json={"title": "Example"})
    assert response.status_code == 201
    path = f"/api/v1/items/{response.json()['id']}"
    assert client.get(path, headers=owner).status_code == 200
    assert client.get("/api/v1/items", headers=other).json() == []
    for method, kwargs in [("get", {}), ("patch", {"json": {"title": "stolen"}}), ("delete", {})]:
        assert getattr(client, method)(path, headers=other, **kwargs).status_code == 404
    assert client.patch(path, headers=owner, json={"title": None}).status_code == 422
    assert client.patch(path, headers=owner, json={"title": "Updated"}).json()["title"] == "Updated"
    assert client.get("/api/v1/items?limit=101", headers=owner).status_code == 422
    assert client.delete(path, headers=owner).status_code == 204
    assert client.get(path, headers=owner).status_code == 404


def test_admin_dependency():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        require_superuser(User(is_superuser=False))
    assert error.value.status_code == 403
    admin = User(is_superuser=True)
    assert require_superuser(admin) is admin


def test_health_and_cors(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    response = client.options(
        "/api/v1/items",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert client.get("/health/live", headers={"Host": "untrusted.example"}).status_code == 400
