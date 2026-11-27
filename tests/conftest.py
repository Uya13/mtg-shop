import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app


@pytest.fixture
def client():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    is_sqlite = url.startswith("sqlite")
    if not is_sqlite and not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError("Тесты разрешены только в отдельной БД с суффиксом _test")
    engine = create_engine(
        url,
        **(
            {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
            if is_sqlite
            else {}
        ),
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def deck_data():
    return {
        "sku": "MTG-001",
        "name": "Учебная зелёная колода",
        "format": "Other",
        "price_rub": "1500.50",
        "cards": [{"name": "Forest", "quantity": 24}],
    }
