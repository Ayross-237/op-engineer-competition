"""Tests for the student pre-order web app (src.web.app).

The web module imports the persistence layer, which builds a Supabase client at
import time, so we stub supabase/psycopg2 and the env BEFORE importing — the same
approach the other suites use. Per test we monkeypatch the individual `helpers`
functions the routes call, so no real DB access happens.
"""
import os
import sys
from datetime import date
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

    def test_rate_requires_login(self, client):
        resp = client.get("/sessions/5/2026-05-02/rate")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# --- sessions list ---

class TestSessionsList:
    # _session_row() is dated 2026-05-02; we move REFERENCE_DATE around it to gate.
    def test_upcoming_session_offers_ordering(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr("src.web.app.REFERENCE_DATE", date(2026, 1, 1))  # session is in the future
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [_session_row()])
        monkeypatch.setattr(helpers, "get_meal_order", lambda sid, pid, d: "Nachos")
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert b"Upcoming sessions" in resp.data
        assert b"Nachos" in resp.data           # the pre-order shows
        assert b"Choose" in resp.data or b"Change" in resp.data

    def test_past_session_offers_rating(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr("src.web.app.REFERENCE_DATE", date(2027, 1, 1))  # session is in the past
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [_session_row()])
        monkeypatch.setattr(helpers, "get_dish_rating_for_session", lambda sid, cid, d: ("Nachos", 8))
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert b"Past sessions" in resp.data
        assert b"8/10" in resp.data
        assert b"Rate" in resp.data

    def test_gating_splits_upcoming_and_past(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr("src.web.app.REFERENCE_DATE", date(2026, 5, 15))
        future = _session_row(program_id=9, date="2026-05-20")
        old = _session_row(program_id=5, date="2026-05-02")
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [future, old])
        monkeypatch.setattr(helpers, "get_meal_order", lambda sid, pid, d: None)
        monkeypatch.setattr(helpers, "get_dish_rating_for_session", lambda sid, cid, d: None)
        resp = client.get("/sessions")
        body = resp.data.decode()
        # The future session links to /order; the past one links to /rate.
        assert "/sessions/9/2026-05-20" in body
        assert "/sessions/5/2026-05-02/rate" in body

    def test_no_sessions_message(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [])
        resp = client.get("/sessions")
        assert b"no upcoming sessions" in resp.data
        assert b"no past sessions" in resp.data


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


# --- ingesting a dish rating ---

class TestRate:
    def _patch_session(self, monkeypatch):
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [_session_row()])
        monkeypatch.setattr(helpers, "get_menu", lambda cid: [("Nachos", ["GF"]), ("Beef Burrito", [])])
        monkeypatch.setattr(helpers, "get_dish_rating_for_session", lambda sid, cid, date: None)
        monkeypatch.setattr(helpers, "get_meal_order", lambda sid, pid, date: None)

    def test_get_renders_rating_form(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        resp = client.get("/sessions/5/2026-05-02/rate")
        assert resp.status_code == 200
        assert b"Nachos" in resp.data
        assert b"Beef Burrito" not in resp.data  # filtered out: not GF
        assert b"Submit rating" in resp.data

    def test_unavailable_session_redirects(self, client, monkeypatch):
        _login(client)
        monkeypatch.setattr(helpers, "get_upcoming_sessions_for_student", lambda sid: [])
        resp = client.post("/sessions/5/2026-05-02/rate", data={"item_name": "Nachos", "rating": "8"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/sessions")

    def test_invalid_dish_rejected(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        record = MagicMock()
        monkeypatch.setattr(helpers, "record_dish_rating", record)
        resp = client.post("/sessions/5/2026-05-02/rate", data={"item_name": "Beef Burrito", "rating": "8"})
        assert resp.status_code == 200
        assert b"choose a dish from your menu" in resp.data
        record.assert_not_called()

    def test_out_of_range_rating_rejected(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        record = MagicMock()
        monkeypatch.setattr(helpers, "record_dish_rating", record)
        resp = client.post("/sessions/5/2026-05-02/rate", data={"item_name": "Nachos", "rating": "11"})
        assert resp.status_code == 200
        assert b"rating from 1 to 10" in resp.data
        record.assert_not_called()

    def test_non_numeric_rating_rejected(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        record = MagicMock()
        monkeypatch.setattr(helpers, "record_dish_rating", record)
        resp = client.post("/sessions/5/2026-05-02/rate", data={"item_name": "Nachos", "rating": "abc"})
        assert resp.status_code == 200
        assert b"rating from 1 to 10" in resp.data
        record.assert_not_called()

    def test_valid_rating_recorded(self, client, monkeypatch):
        _login(client, dietary=["GF"])
        self._patch_session(monkeypatch)
        record = MagicMock()
        monkeypatch.setattr(helpers, "record_dish_rating", record)
        resp = client.post("/sessions/5/2026-05-02/rate", data={"item_name": "Nachos", "rating": "8"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/sessions")
        # record_dish_rating(student_id, caterer_id, date, item_name, rating)
        record.assert_called_once_with(1, 2, "2026-05-02", "Nachos", 8)
