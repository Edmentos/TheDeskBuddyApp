"""Shared fixtures for API tests."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.db import get_db
from app.api import readings
from app.api import settings as settings_api


@pytest.fixture
def client_and_db():
    """Spins up a fresh in-memory SQLite DB and a TestClient for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    test_app = FastAPI()
    test_app.include_router(readings.router)
    test_app.include_router(settings_api.router)
    test_app.dependency_overrides[get_db] = override_get_db

    seed_db = Session()
    with TestClient(test_app) as client:
        yield client, seed_db

    seed_db.close()
    Base.metadata.drop_all(bind=engine)
