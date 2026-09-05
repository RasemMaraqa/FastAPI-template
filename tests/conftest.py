import os

import pytest
from fastapi.testclient import TestClient

# Set before application imports; never use the developer's .env database in tests.
os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-deployment-123456789"
os.environ["ENVIRONMENT"] = "test"
os.environ["ALLOWED_HOSTS"] = '["testserver","localhost"]'
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")

from sqlalchemy.orm import Session  # noqa: E402

from app.database.session import Base, engine  # noqa: E402
from app.dependencies.access import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db():
    # All writes, including route commits, live inside an outer rollback transaction.
    # SQLite needs an explicit BEGIN to keep SAVEPOINT release inside that transaction.
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        transaction = connection.begin()
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN")
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    def create(email="person@example.com"):
        password = "a-strong-password-123"
        response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
        assert response.status_code == 201, response.text
        response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert response.status_code == 200, response.text
        return response.json()

    return create
