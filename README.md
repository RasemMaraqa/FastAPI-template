# FastAPI starter

A reusable backend based on [RasemMaraqa/Project-management](https://github.com/RasemMaraqa/Project-management).
Source reviewed at commit `9774b0236fa25906366a20292e466f8cd867be6f`.
It preserves the original separation of `core`, `database`, `dependencies`, `models`,
`schemas`, and `routers`, with generic users and example items in place of the workspace,
project, and task business logic. This is a fresh database schema, not an upgrade for
the Project-management database.

## Included

- FastAPI with versioned routes and interactive Swagger documentation.
- Registration, login, Argon2 password hashing, JWT access and refresh helpers.
- Single-use refresh-token rotation, session logout, logout everywhere, password changes.
- Active-user and administrator dependencies; owner-scoped CRUD and pagination.
- SQLAlchemy 2, PostgreSQL in Docker, SQLite for convenient local development.
- Alembic initial migration and commands for future schema changes.
- Typed environment configuration, secret validation, explicit CORS and trusted hosts.
- Request IDs, request timing logs, liveness and database readiness endpoints.
- Non-root Docker image, Compose database health checks and a separate migration job.
- Pytest authentication/ownership tests, Ruff formatting/linting, GitHub Actions CI.
- Comments/docstrings explaining the reusable functions and extension points.

## Start locally (PowerShell, Python 3.12+)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python scripts/init_env.py
alembic upgrade head
uvicorn app.main:app --reload
```

If PowerShell prevents activation, use `.\.venv\Scripts\python.exe` in place of
`python`, and run tools as `python -m alembic` / `python -m uvicorn`.
On macOS/Linux activate with `source .venv/bin/activate`.

`init_env.py` generates independent secrets in `.env` and refuses to overwrite it.
Local development uses `app.db`. `.env`, databases, and virtual environments are ignored by Git.
Open [Swagger UI](http://localhost:8000/docs).

## Start with Docker

Install Docker Desktop and start its engine. Generate `.env` with Python as above,
or copy `.env.example` to `.env` and replace both placeholder secrets yourself.
Use a randomly generated SECRET_KEY of at least 32 characters and a URL-safe database
password (letters, digits, `-`, `_`) for Compose's connection URL.

```powershell
docker compose up --build
```

Compose starts PostgreSQL, runs `alembic upgrade head` once, then starts the API at
[localhost:8000/docs](http://localhost:8000/docs). PostgreSQL is private to the Compose
network, and API port 8000 binds to localhost. Data persists in `postgres_data`.

```powershell
docker compose logs -f api
docker compose down
```

`down` keeps database data. Changing POSTGRES_PASSWORD in `.env` does not change the
password in an already initialized database; change that database role password as well.
For an existing running stack after adding a migration:

```powershell
docker compose build
docker compose run --rm migrate
docker compose up -d api
```

## Try authentication

1. In `/docs`, call `POST /api/v1/auth/register`:

   ```json
   {"email": "you@example.com", "password": "choose-a-long-unique-password"}
   ```

2. Click **Authorize**. Enter your email in the **username** field and your password.
   Alternatively call `/api/v1/auth/login` with form data (not JSON):
   `username=you@example.com&password=...`.
3. Call `GET /api/v1/users/me`, or create an item with `{"title":"My first item"}`.
4. Outside Swagger, send `Authorization: Bearer <access_token>` on protected requests.
5. Send `{"refresh_token":"<refresh_token>"}` to `/api/v1/auth/refresh` to get a new pair.
   Replace both stored tokens; the previous refresh token is no longer accepted.

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Create a normal user |
| POST | `/api/v1/auth/login` | Exchange email/password form for tokens |
| POST | `/api/v1/auth/refresh` | Rotate refresh token and issue new access token |
| POST | `/api/v1/auth/logout` | Revoke the supplied refresh token |
| POST | `/api/v1/auth/logout-all` | Revoke all tokens for the authenticated user |
| POST | `/api/v1/auth/change-password` | Change password and revoke all tokens |
| GET | `/api/v1/users/me` | Return authenticated user without password hash |
| GET, POST | `/api/v1/items` | List/create your items |
| GET, PATCH, DELETE | `/api/v1/items/{item_id}` | Read/update/delete your item |
| GET | `/health/live`, `/health/ready` | Process health / database connectivity |

`change-password` accepts `current_password` and `new_password`. Sign in again after
changing it. Item lists accept `offset` and `limit` (maximum 100).

## JWT and password functions

See `app/core/security.py` for the commented implementations:

| Function | How to use it |
| --- | --- |
| `hash_password(password)` | Hash a plaintext password before saving it |
| `verify_password(password, stored_hash)` | Verify login or password-change credentials |
| `create_access_token(user_id, version)` | Issue a short-lived signed access token |
| `create_refresh_token(user_id, version)` | Low-level refresh signing; use `issue_tokens` in routes |
| `decode_token(token, expected_type)` | Validate signature and claims; raises `jwt.InvalidTokenError` |
| `issue_tokens(db, user)` | Create both tokens and stage a refresh-session record; then commit |
| `consume_refresh(db, token)` | Atomically consume a refresh token before rotation/logout |
| `get_current_user(...)` | Validate access token and load an active user from the database |
| `require_superuser(user)` | Reject users without the database administrator flag |

Tokens include `sub`, `exp`, `iat`, `jti`, `type`, `ver`, `iss`, and `aud`. HS256 is fixed
on the server. Refresh tokens cannot be used as access tokens. JWT payloads are signed,
not encrypted. Passwords are Argon2 hashes; refresh sessions store random identifiers,
not bearer tokens. Defaults: access lifetime 15 minutes, refresh lifetime 7 days.
Each rotation starts a fresh 7-day period; there is no absolute session lifetime.

Session logout revokes only the supplied refresh token. Its access token remains valid
until expiry. Logout-all and password changes increment the user's token version,
which invalidates all previously issued tokens on subsequent authentication checks.
Already running requests may finish. Reusing an old refresh token is rejected; it does
not automatically revoke the replacement token or the entire session family.

The JWT/hash approach follows the [FastAPI security guide](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
using PyJWT in place of the original repository's python-jose.

## Add a protected feature

Keep this structure and copy the item example for a new resource:

```text
app/
  core/          Configuration and JWT/password primitives
  database/      Declarative base, engine, per-request sessions
  dependencies/  CurrentUser, AdminUser, DbSession
  models/        Database tables (import new models in __init__.py)
  schemas/       Validated request bodies and public response shapes
  services/      Shared business logic and auth transactions
  routers/       HTTP routes grouped by feature
  main.py        App assembly, middleware, health, router registration
  cli.py         Local administrator operations
alembic/         Database schema history
scripts/         Project setup helpers
tests/           API and authorization regression tests
```

Example `app/routers/reports.py`:

```python
from fastapi import APIRouter
from app.dependencies.access import AdminUser, CurrentUser

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/mine")
def my_report(user: CurrentUser):
    # CurrentUser enforces login. Filter database queries using user.id.
    return {"user_id": user.id}


@router.get("/admin")
def admin_report(admin: AdminUser):
    # Public registration cannot grant this privilege.
    return {"message": "Administrator access confirmed"}
```

Import and register `reports.router` in `app/main.py` with `prefix="/api/v1"`.
For database access, add `db: DbSession`. Writes call `db.commit()` explicitly;
return response schemas to avoid leaking model fields. PATCH uses `exclude_unset=True`
so omitted fields keep their existing values. A user cannot choose `owner_id`.

Promote a registered account from a trusted local shell:

```powershell
python -m app.cli promote you@example.com
# Or: docker compose exec api python -m app.cli promote you@example.com
```

For organization/team permissions, add role and membership models and dependencies
specific to that domain. The original repository's workspace policy model is useful
for those projects, but this starter deliberately uses generic administrator/ownership checks.

## Database changes

Add/change models, import them through `app/models/__init__.py`, then:

```powershell
alembic revision --autogenerate -m "add reports"
# Review the generated migration, especially renames and destructive operations.
alembic upgrade head
alembic check
```

Use a disposable development database for `alembic downgrade -1`; downgrades can delete
data. Application startup never calls `create_all`; migrations are the schema authority.
Use `postgresql+psycopg://user:password@host:5432/database` for local PostgreSQL.
Percent-encode special characters in manually constructed database URLs.

## Tests and code quality

```powershell
pytest -q
ruff check .
ruff format --check .
```

Tests use an isolated SQLite connection by default and roll back their writes. To test
PostgreSQL, set `TEST_DATABASE_URL` to a **dedicated test database**, then run the same command.
Tests create missing schema there. Never point tests at a production database.
CI runs SQLite and PostgreSQL tests, migration upgrade/check/downgrade, and a Docker build.
Dependency files define compatible ranges; for deployment, generate and maintain a
platform-appropriate lockfile after reviewing updates.

## Reuse for each new project

Copy this folder without `.venv`, `.env`, databases, caches, or `.source-reference`.
The latter is the downloaded source inspection checkout and is not part of the starter.
Generate a new `.env`; change APP_NAME, JWT_ISSUER, JWT_AUDIENCE, CORS_ORIGINS, and
ALLOWED_HOSTS. Remove/rename the example Item model, schema and router as needed.
For a brand-new unpublished project you can replace the initial migration; once a
database has been deployed, add migrations instead of rewriting its history.

You can also push the starter to your own GitHub repository and enable **Template
repository** in that repository's settings, then use **Use this template** for new projects.

## Deployment-specific additions

Set ENVIRONMENT=production (disables public API docs), configure your real allowed host
and frontend origins, and supply secrets through your deployment's secret manager.
Put TLS and shared rate limiting in front of login/registration/refresh endpoints.
This starter does not include a distributed rate limiter, email verification, forgotten
password email delivery, MFA, social login, or frontend token storage. Those require
product/provider choices. Browser cookie authentication additionally needs CSRF defenses;
these endpoints currently use bearer headers and JSON refresh tokens.

Run migrations as one release job, arrange PostgreSQL backups and monitoring, and
schedule `python -m app.cli cleanup-sessions` to remove expired session records.
The readiness check verifies database connectivity, not migration currency. Request
logs exclude bodies and credentials; add an error-reporting integration for production.
