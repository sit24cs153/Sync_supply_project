import os
import sys
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_syncsupply.db")
os.environ.setdefault("OTP_PROVIDER", "console")
# Tests hammer auth endpoints from a single client IP far faster than any
# real user would — raise the limiter ceiling so tests exercise behavior,
# not the rate limiter itself (that has its own dedicated test).
os.environ.setdefault("RATE_LIMIT_AUTH", "1000/minute")
os.environ.setdefault("RATE_LIMIT_SYMPTOMS", "1000/minute")
os.environ.setdefault("TRIAL_STARTS_PER_IP_PER_DAY", "1000")
# TestClient talks to the app over plain http://testserver; a Secure cookie
# would never be echoed back by the client, breaking the cookie-identity
# tests for a reason that has nothing to do with the behavior under test.
os.environ.setdefault("COOKIE_SECURE", "false")

from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, get_db, SessionLocal
from app.data_loader import ensure_dataset_loaded


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_dataset_loaded(db)
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def trial_headers(client):
    """
    Trial identity is now server-managed via an HttpOnly cookie; TestClient
    keeps cookies across requests made on the same client instance, so a
    fresh `client` per test gives a fresh, isolated trial identity.
    """
    resp = client.post("/api/auth/trial", json=None)
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
