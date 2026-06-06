"""Tests for the student pre-order web app (src.web.app).

The web module imports the persistence layer, which builds a Supabase client at
import time, so we stub supabase/psycopg2 and the env BEFORE importing — the same
approach the other suites use. Per test we monkeypatch the individual `helpers`
functions the routes call, so no real DB access happens.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.modules["ollama"] = MagicMock()
sys.modules["supabase"] = MagicMock()
sys.modules["psycopg2"] = MagicMock()
os.environ.setdefault("SUPABASE_URL", "http://test.local")
os.environ.setdefault("SUPABASE_KEY", "test-key")

from src.web.app import create_app  # noqa: E402
from src.persistence import helpers  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def _login(client, student_id=1, dietary=None):
    """Seed a logged-in session without going through the email lookup."""
    with client.session_transaction() as sess:
        sess["student_id"] = student_id
        sess["student_name"] = "Test Student"
        sess["dietary"] = dietary if dietary is not None else []
        sess["dietary_extra"] = None


def _session_row(**kw):
    row = dict(
        program_id=5, date="2026-05-02", school_name="John Paul College",
        caterer_id=2, day="Tuesday", start="16:00:00", end="19:00:00",
        dinner="18:00:00", building="G Centre",
    )
    row.update(kw)
    return row


# --- login ---

class TestLogin:
    def test_unknown_email_shows_error(self, client, monkeypatch):
        monkeypatch.setattr(helpers, "get_student_by_email", lambda email: None)
        resp = client.post("/login", data={"email": "nobody@x.com"})
        assert resp.status_code == 200
        assert b"No student found" in resp.data
        with client.session_transaction() as sess:
            assert "student_id" not in sess

    def test_known_email_sets_session_and_redirects(self, client, monkeypatch):
        monkeypatch.setattr(helpers, "get_student_by_email", lambda email: (1, "Ann", ["GF"], None))
        resp = client.post("/login", data={"email": "ann@x.com"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/sessions")
        with client.session_transaction() as sess:
            assert sess["student_id"] == 1
            assert sess["dietary"] == ["GF"]


# --- auth gate ---

class TestAuthGate:
    def test_sessions_requires_login(self, client):
        resp = client.get("/sessions")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_order_requires_login(self, client):
        resp = client.get("/sessions/5/2026-05-02")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# --- sessions list ---

class TestSessionsList:
    def test_lists_sessions_with_order_status(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [_session_row()])
        monkeypatch.setattr(helpers, "get_meal_order", lambda sid, pid, date: "Nachos")
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert b"Nachos" in resp.data
        assert b"John Paul College" in resp.data

    def test_no_sessions_message(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [])
        resp = client.get("/sessions")
        assert b"no upcoming sessions" in resp.data


# --- placing / changing / clearing an order ---

class TestOrder:
    def _patch_session(self, monkeypatch, dietary=None):
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [_session_row()])
        monkeypatch.setattr(helpers, "get_menu", lambda cid: [("Nachos", ["GF"]), ("Beef Burrito", [])])
        monkeypatch.setattr(helpers, "get_meal_order", lambda sid, pid, date: None)

    def test_get_renders_filtered_menu(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        resp = client.get("/sessions/5/2026-05-02")
        assert resp.status_code == 200
        assert b"Nachos" in resp.data
        assert b"Beef Burrito" not in resp.data  # filtered out: not GF

    def test_unavailable_session_redirects(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [])
        resp = client.post("/sessions/5/2026-05-02", data={"action": "set", "item_name": "Nachos"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/sessions")

    def test_invalid_dish_rejected(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        upsert = MagicMock()
        monkeypatch.setattr(helpers, "upsert_meal_order", upsert)
        # "Beef Burrito" is filtered out for a GF student → not an allowed choice.
        resp = client.post("/sessions/5/2026-05-02", data={"action": "set", "item_name": "Beef Burrito"})
        assert resp.status_code == 200
        assert b"choose a dish from your menu" in resp.data
        upsert.assert_not_called()

    def test_valid_dish_upserts(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        upsert = MagicMock()
        monkeypatch.setattr(helpers, "upsert_meal_order", upsert)
        resp = client.post("/sessions/5/2026-05-02", data={"action": "set", "item_name": "Nachos"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/sessions")
        upsert.assert_called_once_with(1, 5, "2026-05-02", 2, "Nachos")

    def test_clear_deletes(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        delete = MagicMock()
        monkeypatch.setattr(helpers, "delete_meal_order", delete)
        resp = client.post("/sessions/5/2026-05-02", data={"action": "clear"})
        assert resp.status_code == 302
        delete.assert_called_once_with(1, 5, "2026-05-02")
