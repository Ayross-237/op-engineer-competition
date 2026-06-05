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

from src.business.create_orders import (  # noqa: E402
    RenderedSession,
    SessionReport,
    slug,
    build_caterer_order,
    render_session,
    render_session_block,
)


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
