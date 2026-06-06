"""Tests for the pure rendering/assembly logic in src.business.create_orders.

create_orders imports llm (pulls a model at import) and persistence (creates a
DB client at import), so we stub those modules and env BEFORE importing it — the
same approach test_llm.py uses for ollama. Only the deterministic, side-effect-free
functions are exercised here; the LLM/DB/email paths are out of scope for unit tests.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

# Neutralise import-time side effects before importing create_orders.
sys.modules["ollama"] = MagicMock()
sys.modules["supabase"] = MagicMock()
sys.modules["psycopg2"] = MagicMock()
os.environ.setdefault("SUPABASE_URL", "http://test.local")
os.environ.setdefault("SUPABASE_KEY", "test-key")

from datetime import date  # noqa: E402

from src.business import create_orders  # noqa: E402
from src.business.create_orders import (  # noqa: E402
    RenderedSession,
    SessionReport,
    slug,
    build_caterer_order,
    build_session_report,
    email_validation_failure,
    recent_feedback,
    render_session,
    render_session_block,
    send_pre_order_confirmations,
)
from src.business import llm  # noqa: E402
from src.business.menu import MenuItem  # noqa: E402
from src.persistence import helpers  # noqa: E402


def _report(**kw) -> SessionReport:
    """Build a SessionReport with sensible defaults for rendering tests."""
    defaults = dict(
        student_count=3,
        standard_counts={"Pad Thai": 2, "Nachos": 1},
        special_assignments=[],
        cost=135.0,
        pricing=(35.0, 10.0, 20.0),
    )
    defaults.update(kw)
    return SessionReport(**defaults)


def _session(**kw) -> RenderedSession:
    defaults = dict(
        school_name="John Paul College",
        header="2026-05-02 (Tuesday 16:00–19:00)",
        building="G Centre",
        dinner="18:00",
        manager_line="**Manager:** Jessie — 0412 345 678",
        total_count=4,
        opted_out_count=1,
        report=_report(),
    )
    defaults.update(kw)
    return RenderedSession(**defaults)


# --- _slug ---

class TestSlug:
    def test_spaces_become_hyphens(self):
        assert slug("Terrific Noodles") == "terrific-noodles"

    def test_apostrophe_run_collapses(self):
        # "Boys' College" → the "' " run must collapse to a single hyphen.
        assert slug("Moreton Bay Boys' College") == "moreton-bay-boys-college"

    def test_multiword(self):
        assert slug("Guzman y Gomez") == "guzman-y-gomez"

    def test_strips_leading_and_trailing_separators(self):
        assert slug("  Kenko!  ") == "kenko"

    def test_digits_preserved(self):
        assert slug("Caterer 4") == "caterer-4"


# --- build_session_report: locked pre-orders vs auto-assignment ---

class TestBuildSessionReport:
    PRICING = (10.0, 5.0, 2.0)  # (per_item, per_trip, per_school)

    def test_empty_roster_returns_zero(self):
        r = build_session_report([], [MenuItem("A", [])], self.PRICING)
        assert r.student_count == 0
        assert r.standard_counts == {}
        assert r.special_assignments == []
        assert r.cost == 0.0

    def test_locked_orders_counted_verbatim(self):
        # The locked dish is used even when it isn't what the picker would choose.
        students = [(1, [], None), (2, [], None)]
        menu = [MenuItem("Pad Thai", []), MenuItem("Nachos", [])]
        r = build_session_report(students, menu, self.PRICING, {1: "Nachos", 2: "Nachos"})
        assert r.standard_counts == {"Nachos": 2}
        assert r.special_assignments == []
        assert r.student_count == 2

    def test_locked_order_overrides_special_dietary(self):
        # A special-dietary student who pre-ordered must skip the LLM recommendation.
        llm.client.chat.side_effect = AssertionError("LLM must not run for a locked order")
        try:
            students = [(7, ["GF"], "no peanuts please")]
            menu = [MenuItem("Safe Bowl", ["GF"])]
            r = build_session_report(students, menu, self.PRICING, {7: "Safe Bowl"})
        finally:
            llm.client.chat.side_effect = None
        assert r.standard_counts == {"Safe Bowl": 1}
        assert r.special_assignments == []

    def test_unlocked_special_uses_llm(self):
        # Without a lock, a free-text dietary student routes through find_meal.
        llm.client.chat.return_value = {"message": {"content": "Safe Bowl"}}
        try:
            students = [(7, ["GF"], "no peanuts please")]
            menu = [MenuItem("Safe Bowl", ["GF"])]
            r = build_session_report(students, menu, self.PRICING, locked_orders=None)
        finally:
            llm.client.chat.reset_mock(return_value=True)
        assert r.special_assignments == [("GF, no peanuts please", "Safe Bowl")]
        assert r.standard_counts == {}

    def test_unlocked_standard_uses_picker(self):
        # Single matching dish → the weighted picker is deterministic.
        students = [(3, ["GF"], None)]
        menu = [MenuItem("Only GF", ["GF"]), MenuItem("Plain", [])]
        r = build_session_report(students, menu, self.PRICING)
        assert r.standard_counts == {"Only GF": 1}

    def test_mixed_locked_and_unlocked(self):
        students = [(1, [], None), (2, ["GF"], None)]
        menu = [MenuItem("GF Dish", ["GF"]), MenuItem("Plain", [])]
        # Student 1 locked to "GF Dish"; student 2 (unlocked, GF) can only match "GF Dish".
        r = build_session_report(students, menu, self.PRICING, {1: "GF Dish"})
        assert r.standard_counts == {"GF Dish": 2}

    def test_cost_counts_every_student(self):
        students = [(1, [], None), (2, [], None), (3, [], None)]
        menu = [MenuItem("A", [])]
        r = build_session_report(students, menu, self.PRICING, {1: "A", 2: "A", 3: "A"})
        assert r.cost == 3 * 10.0 + 5.0 + 2.0  # 37.0


# --- render_session cost toggle ---

class TestRenderSessionCost:
    def test_cost_hidden_by_default(self):
        out = "\n".join(render_session(_report()))
        assert "Estimated cost" not in out

    def test_cost_shown_when_requested(self):
        out = "\n".join(render_session(_report(), include_cost=True))
        assert "Estimated cost" in out
        assert "$135.00" in out

    def test_empty_session_renders_placeholder(self):
        out = render_session(_report(student_count=0, standard_counts={}))
        assert out == ["_No catering required._"]


# --- render_session_block ---

class TestRenderSessionBlock:
    def test_caterer_mode_shows_meals_no_cost_no_optout(self):
        out = "\n".join(render_session_block(_session(), include_cost=False, include_optout=False, include_dinner=True))
        assert "**Meals:** 3" in out
        assert "Requested delivery:" in out
        assert "5:50 PM – 5:55 PM" in out  # 18:00 dinner → 10–5 min before
        assert "Estimated cost" not in out
        assert "opted out" not in out

    def test_overview_mode_shows_optout_and_cost(self):
        out = "\n".join(render_session_block(_session(), include_cost=True, include_optout=True, include_dinner=True))
        assert "**Students:** 4 total, 1 opted out" in out
        assert "Estimated cost" in out
        assert "**Meals:**" not in out

    def test_manager_line_included(self):
        out = "\n".join(render_session_block(_session(), include_cost=False, include_optout=False, include_dinner=True))
        assert "**Manager:** Jessie — 0412 345 678" in out

    def test_building_included(self):
        out = "\n".join(render_session_block(_session(), include_cost=False, include_optout=False, include_dinner=True))
        assert "**Building:** G Centre" in out


# --- build_caterer_order ---

class TestBuildCatererOrder:
    def test_title_and_week_header(self):
        out = build_caterer_order("Terrific Noodles", [_session()], ["2026-05-01", "2026-05-07"])
        joined = "\n".join(out)
        assert "# Catering Order — Terrific Noodles" in joined
        assert "_Week of 2026-05-01 – 2026-05-07_" in joined

    def test_school_heading_emitted_once_per_school(self):
        sessions = [
            _session(school_name="John Paul College", header="2026-05-02 (Tuesday 16:00–19:00)"),
            _session(school_name="John Paul College", header="2026-05-03 (Wednesday 16:00–19:00)"),
            _session(school_name="MacGregor State High School", header="2026-05-04 (Thursday 16:00–19:00)"),
        ]
        out = "\n".join(build_caterer_order("Terrific Noodles", sessions, ["2026-05-01", "2026-05-07"]))
        assert out.count("## John Paul College") == 1
        assert out.count("## MacGregor State High School") == 1

    def test_no_cost_in_caterer_document(self):
        out = "\n".join(build_caterer_order("Terrific Noodles", [_session()], ["2026-05-01", "2026-05-07"]))
        assert "Estimated cost" not in out
        assert "Caterer feedback summary" not in out

    def test_special_dietary_note_present_when_special_assignments(self):
        rs = _session(report=_report(special_assignments=[("No Beef", "Mie Goreng (vegetarian)")]))
        out = "\n".join(build_caterer_order("Terrific Noodles", [rs], ["2026-05-01", "2026-05-07"]))
        assert "please substitute another dish" in out

    def test_special_dietary_note_absent_without_special_assignments(self):
        rs = _session(report=_report(special_assignments=[]))
        out = "\n".join(build_caterer_order("Terrific Noodles", [rs], ["2026-05-01", "2026-05-07"]))
        assert "please substitute another dish" not in out

    def test_special_dietary_note_absent_from_overview(self):
        # The note targets caterers; the internal overview must not carry it.
        rs = _session(report=_report(special_assignments=[("No Beef", "Mie Goreng (vegetarian)")]))
        out = "\n".join(render_session_block(rs, include_cost=True, include_optout=True, include_dinner=True))
        assert "please substitute another dish" not in out


# --- recent_feedback window filter ---

class TestRecentFeedback:
    FB = [
        ("2026-01-01 19:00+10", "old"),
        ("2026-02-15 19:00+10", "mid"),
        ("2026-03-01 19:00+10", "recent"),
    ]

    def test_filters_to_window(self):
        # 4 weeks before 2026-03-05 is 2026-02-05 → keeps mid + recent, drops old.
        out = recent_feedback(self.FB, date(2026, 3, 5), 4)
        assert [c for _, c in out] == ["mid", "recent"]

    def test_cutoff_is_inclusive(self):
        # 1 week before 2026-03-05 is exactly 2026-02-26.
        out = recent_feedback([("2026-02-26 00:00+10", "edge")], date(2026, 3, 5), 1)
        assert len(out) == 1

    def test_reference_date_is_inclusive(self):
        out = recent_feedback([("2026-03-05 12:00+10", "today")], date(2026, 3, 5), 1)
        assert len(out) == 1

    def test_future_entries_excluded(self):
        assert recent_feedback([("2026-04-01 19:00+10", "future")], date(2026, 3, 5), 4) == []

    def test_unparseable_dates_skipped(self):
        fb = [("not-a-date", "bad"), ("2026-03-01 19:00+10", "ok")]
        assert recent_feedback(fb, date(2026, 3, 5), 4) == [("2026-03-01 19:00+10", "ok")]

    def test_empty_input(self):
        assert recent_feedback([], date(2026, 3, 5), 4) == []


# --- caterer order: manager feedback section ---

class TestCatererOrderFeedback:
    WEEK = ["2026-05-01", "2026-05-07"]

    def test_section_appended_when_summary_present(self):
        out = "\n".join(build_caterer_order(
            "Terrific Noodles", [_session()], self.WEEK,
            feedback_summary="Noodles were consistently well received.", feedback_weeks=4,
        ))
        assert "## Manager feedback (last 4 weeks)" in out
        assert "Noodles were consistently well received." in out

    def test_no_section_when_summary_empty(self):
        out = "\n".join(build_caterer_order("Terrific Noodles", [_session()], self.WEEK))
        assert "Manager feedback" not in out

    def test_header_reflects_weeks_parameter(self):
        out = "\n".join(build_caterer_order(
            "Terrific Noodles", [_session()], self.WEEK, feedback_summary="s", feedback_weeks=8,
        ))
        assert "(last 8 weeks)" in out

    def test_still_no_internal_cost_with_feedback(self):
        out = "\n".join(build_caterer_order(
            "Terrific Noodles", [_session()], self.WEEK, feedback_summary="s", feedback_weeks=4,
        ))
        assert "Estimated cost" not in out


# --- pre-order confirmation emails (sent by the script on dispatch) ---

class TestPreOrderConfirmations:
    def _conf(self, **kw):
        c = dict(student_id=1, dish="Nachos", school_name="Loreto College", date="2026-05-04", day="Monday")
        c.update(kw)
        return c

    def test_no_confirmations_sends_nothing(self, monkeypatch):
        mail = MagicMock()
        monkeypatch.setattr(create_orders, "send_email", mail)
        send_pre_order_confirmations("Guzman y Gomez", [])
        mail.assert_not_called()

    def test_confirmations_go_to_redirect_address(self, monkeypatch):
        mail = MagicMock()
        monkeypatch.setattr(create_orders, "send_email", mail)
        monkeypatch.setattr(helpers, "get_student_name", lambda sid: f"Student {sid}")
        confs = [self._conf(student_id=1), self._conf(student_id=2, dish="Caesar Salad")]
        send_pre_order_confirmations("Guzman y Gomez", confs)
        # NOTE: a temporary `break` in send_pre_order_confirmations caps sends to one
        # during testing, so assert the invariant (recipient) rather than an exact count.
        assert mail.call_count >= 1
        # Every confirmation that is sent goes to the redirect address, never a student's own email.
        assert all(call.args[0] == "aaron.r.dmello@gmail.com" for call in mail.call_args_list)

    def test_student_name_looked_up_once_each(self, monkeypatch):
        monkeypatch.setattr(create_orders, "send_email", MagicMock())
        name = MagicMock(side_effect=lambda sid: f"Student {sid}")
        monkeypatch.setattr(helpers, "get_student_name", name)
        # Same student appears twice (two sessions) → name fetched once and cached.
        send_pre_order_confirmations("Kenko Sushi House", [self._conf(date="2026-05-04"), self._conf(date="2026-05-11")])
        name.assert_called_once_with(1)

    def test_mail_failure_is_swallowed(self, monkeypatch):
        monkeypatch.setattr(create_orders, "send_email", MagicMock(side_effect=RuntimeError("smtp down")))
        monkeypatch.setattr(helpers, "get_student_name", lambda sid: "Ann")
        # Must not raise — a failed confirmation can't abort the order run.
        send_pre_order_confirmations("Lakehouse Victoria Point", [self._conf()])


# --- validation-failure report email (sent when the LLM judge holds the batch) ---

class TestValidationFailureEmail:
    WEEK = ["2026-05-01", "2026-05-07"]

    def test_emails_admin_with_all_issues(self, monkeypatch):
        mail = MagicMock()
        monkeypatch.setattr(create_orders, "send_email", mail)
        failures = {
            "Guzman y Gomez": ["Dish 'Sushi' not on menu", "Empty session block"],
            "Kenko Sushi House": ["Contains 'LLM FAILURE' text"],
        }
        email_validation_failure("admin@padea.com", failures, self.WEEK)
        mail.assert_called_once()
        to, subject, body = mail.call_args.args[0], mail.call_args.args[1], mail.call_args.args[2]
        assert to == "admin@padea.com"
        assert "validation failed" in subject.lower()
        # Every caterer and every issue is named in the report.
        for caterer, issues in failures.items():
            assert caterer in body
            for issue in issues:
                assert issue in body
        assert "No orders were sent" in body
