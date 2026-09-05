# FastAPI Template

A starter for FastAPI projects with authentication, a database, Docker, and example CRUD routes.

## Run locally

Requires Python 3.12 or newer. Run these commands from the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python scripts/init_env.py
alembic upgrade head
uvicorn app.main:app --reload
```

On macOS/Linux, activate the environment with `source .venv/bin/activate`.
If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m` before
`pip`, `alembic`, or `uvicorn` instead.

The setup script creates `.env` with random secrets. If `.env` already exists,
it leaves it unchanged. Local development uses SQLite by default.

Open [http://localhost:8000/docs](http://localhost:8000/docs) to try the API.

## Run with Docker

Start Docker Desktop, then run:

```powershell
python scripts/init_env.py
docker compose up --build
```

Skip the first command if you already have `.env`. You can also copy `.env.example`
to `.env` and replace the secret and database password manually. Use a random
`SECRET_KEY` of at least 32 characters and a URL-safe database password.

Docker starts PostgreSQL, applies migrations, and starts the API at
[http://localhost:8000/docs](http://localhost:8000/docs).

```powershell
# View API logs
docker compose logs -f api

# Stop containers and keep database data
docker compose down
```

After adding a migration to an existing stack:

```powershell
docker compose build
docker compose run --rm migrate
docker compose up -d api
```

Database data stays in a Docker volume. Changing `POSTGRES_PASSWORD` in `.env`
after the database has been created also requires changing the database role's password.

## Configuration

Edit `.env` for your project:

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | API title |
| `ENVIRONMENT` | `development`, `test`, or `production`; production disables API docs |
| `DATABASE_URL` | Database connection URL; Docker sets this automatically |
| `SECRET_KEY` | Secret used to sign JWTs; generate a new one for each project |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime, default 15 minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime, default 7 days |
| `JWT_ISSUER` | Name identifying the token issuer |
| `JWT_AUDIENCE` | Name identifying the API accepting the token |
| `CORS_ORIGINS` | Frontend origins as a JSON array, such as `["http://localhost:3000"]` |
| `ALLOWED_HOSTS` | API hostnames as a JSON array |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Docker database credentials |

For local PostgreSQL, set `DATABASE_URL` to
`postgresql+psycopg://user:password@localhost:5432/database`.
Percent-encode special characters in manually constructed connection URLs.
Keep `.env` out of version control.

## Authentication

1. Open `/docs` and call `POST /api/v1/auth/register`:

   ```json
   {
     "email": "you@example.com",
     "password": "choose-a-long-unique-password"
   }
   ```

2. Click **Authorize** and enter your email in the **username** field, then your password.
3. Try `GET /api/v1/users/me` or the item routes.

To log in from a client, send form data to `POST /api/v1/auth/login` with
`username` set to the email address and `password` set to the password.
The response contains `access_token` and `refresh_token`.

Send the access token on protected requests:

```text
Authorization: Bearer <access_token>
```

To renew your tokens, send this JSON to `POST /api/v1/auth/refresh`:

```json
{"refresh_token": "<refresh_token>"}
```

Save both new tokens. Each refresh token can only be used once.

- `/auth/logout` accepts the same JSON and revokes that refresh token. Its access token remains valid until expiry.
- `/auth/logout-all` requires an access token and invalidates all tokens for the account.
- `/auth/change-password` requires an access token and a JSON body with `current_password` and `new_password`. Sign in again afterward.

All authentication routes use the `/api/v1` prefix. Passwords must be 12–128 characters.

## Routes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Create an account |
| POST | `/api/v1/auth/login` | Sign in |
| POST | `/api/v1/auth/refresh` | Get a new token pair |
| POST | `/api/v1/auth/logout` | Sign out of a session |
| POST | `/api/v1/auth/logout-all` | Sign out everywhere |
| POST | `/api/v1/auth/change-password` | Change your password |
| GET | `/api/v1/users/me` | Get your account |
| GET, POST | `/api/v1/items` | List or create your items |
| GET, PATCH, DELETE | `/api/v1/items/{item_id}` | Read, update, or delete your item |
| GET | `/health/live` | Check that the API is running |
| GET | `/health/ready` | Check the database connection |

Create an item with `{"title": "My first item", "description": "Optional description"}`.
Item lists accept `offset` and `limit`, with a maximum limit of 100.
Users can only access their own items.

## Project structure

```text
app/
  core/          Configuration and JWT/password functions
  database/      Database engine, sessions, and model base
  dependencies/  Authentication and administrator checks
  models/        SQLAlchemy database models
  schemas/       Request and response schemas
  services/      Shared business logic
  routers/       API endpoints
  main.py        App setup and router registration
  cli.py         Administrator commands
alembic/         Database migrations
scripts/         Setup helpers
tests/           API tests
```

## Add a route

Create a router in `app/routers/`. Use `CurrentUser` to require authentication,
`AdminUser` to require administrator access, and `DbSession` for database access:

```python
from fastapi import APIRouter
from app.dependencies.access import AdminUser, CurrentUser

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/mine")
def my_report(user: CurrentUser):
    return {"user_id": user.id}


@router.get("/admin")
def admin_report(admin: AdminUser):
    return {"message": "Administrator access confirmed"}
```

Import the router in `app/main.py` and register it:

```python
from app.routers import reports

app.include_router(reports.router, prefix="/api/v1")
```

Use the item routes as an example for database CRUD. Filter user-owned records by
`user.id`, call `db.commit()` to save changes, and define response schemas for returned data.

To make an existing account an administrator:

```powershell
python -m app.cli promote you@example.com
# With Docker:
docker compose exec api python -m app.cli promote you@example.com
```

## Password and JWT helpers

Password and JWT functions are in `app/core/security.py`. Token session handling
is in `app/services/auth.py`.

| Function | Usage |
| --- | --- |
| `hash_password(password)` | Hash a password before saving it |
| `verify_password(password, stored_hash)` | Check a password against its stored hash |
| `create_access_token(user_id, version)` | Create an access token using the user's token version |
| `create_refresh_token(user_id, version)` | Create a refresh token; use `issue_tokens` when issuing a session |
| `decode_token(token, expected_type)` | Validate a token; raises `jwt.InvalidTokenError` on failure |
| `issue_tokens(db, user)` | Create a token pair and stage its refresh session; commit afterward |
| `consume_refresh(db, token)` | Consume a refresh token during renewal or logout |

For protected routes, use `CurrentUser` rather than decoding tokens yourself.
Do not put passwords or private data in JWT payloads.

## Database migrations

After changing models, make sure they are imported in `app/models/__init__.py`, then run:

```powershell
alembic revision --autogenerate -m "describe your change"
```

Review the generated migration before applying it:

```powershell
alembic upgrade head
alembic check
```

Add new migrations for deployed databases instead of editing migrations already applied.

## Tests and formatting

```powershell
pytest -q
ruff check .
ruff format .
```

Tests use isolated SQLite by default. To test against PostgreSQL, set
`TEST_DATABASE_URL` to a dedicated test database. Tests create missing tables there;
never use a production database.

GitHub Actions runs tests, linting, formatting checks, migrations, and a Docker build.

## Start a new project

Copy the template without `.env`, `.venv`, local databases, caches, or `.source-reference`.
Run the setup commands to generate fresh secrets and create your database.
Update the app name, JWT issuer/audience, allowed hosts, and frontend origins in `.env`.
Replace the example item model, schemas, and routes with your own features.

## Deployment

Set `ENVIRONMENT=production`, configure your domain and frontend origins, and provide
secrets through your hosting platform. Use HTTPS and add rate limiting for authentication
endpoints. Email verification, password recovery, and social login can be added as needed.

Run migrations before starting the new API version and arrange database backups.
Periodically remove expired refresh sessions:

```powershell
python -m app.cli cleanup-sessions
```
