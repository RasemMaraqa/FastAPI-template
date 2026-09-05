import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_settings
from app.dependencies.access import DbSession
from app.routers import auth, items, users

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")
app = FastAPI(
    title=settings.app_name,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_logging(request, call_next):
    request_id = uuid4().hex
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    # Never log bodies, passwords, Authorization headers or query-string secrets.
    logger.info(
        "request_id=%s method=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        response.status_code,
        (time.perf_counter() - start) * 1000,
    )
    return response


@app.get("/health/live", tags=["Health"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
def ready(db: DbSession):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ok"}


# Register new feature routers here; keep business logic out of main.py.
for router in (auth.router, users.router, items.router):
    app.include_router(router, prefix="/api/v1")
