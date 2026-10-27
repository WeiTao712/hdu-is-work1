"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.security import clear_revocations  # noqa: E402
import app.security as security  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    class Config(TestConfig):
        DATABASE_PATH = str(tmp_path / "test.db")

    application = create_app(Config)
    security._ATTEMPTS.clear()
    clear_revocations()
    yield application
    security._ATTEMPTS.clear()
    clear_revocations()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def token(client):
    resp = client.post("/auth/login", json={"username": "demo", "password": "DemoPassw0rd!2024"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["access_token"]


@pytest.fixture()
def auth(token):
    return {"Authorization": f"Bearer {token}"}
