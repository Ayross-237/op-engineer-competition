"""Tests for src.business.llm.

llm.py has heavy module-level side effects: it pulls a model and pins it in
RAM at import time. We replace the `ollama` module in sys.modules BEFORE
importing llm so those calls become no-op MagicMock invocations and never
touch the network. Per-test, we set `llm.client.chat.return_value` to canned
responses to drive the LLM-facing functions deterministically.
"""
import sys
from unittest.mock import MagicMock

import pytest

# Replace `ollama` BEFORE src.business.llm imports it (the module pulls a model
# and pins it in memory at import time).
sys.modules["ollama"] = MagicMock()

# These imports must come after the sys.modules patch.
from src.business import llm  # noqa: E402
from src.business.menu import MenuItem  # noqa: E402


def _chat_returning(text: str):
    """Helper: build a chat response shaped like the Ollama client returns."""
    return {"message": {"content": text}}


@pytest.fixture(autouse=True)
def _reset_chat_mock():
    """Reset chat mock state between every test. reset_mock() preserves
    side_effect by default, so a one-shot iterator from one test would
    raise StopIteration in the next without this teardown."""
    yield
    llm.client.chat.reset_mock()
    llm.client.chat.side_effect = None


# --- find_meal ---

class TestFindMeal:
    def test_empty_menu_returns_sentinel(self):
        result = llm.find_meal("any notes", [])
        assert result == "NO MEAL AVAILABLE"

    def test_exact_match_returned_verbatim(self):
        llm.client.chat.return_value = _chat_returning("Pad Thai")
        menu = [MenuItem("Pad Thai", ["GF"]), MenuItem("Caesar Salad", ["V"])]
        assert llm.find_meal("loves noodles", menu) == "Pad Thai"

    def test_substring_match_normalised_to_menu_name(self):
        # LLM wraps the name in extra prose; substring containment recovers it.
        llm.client.chat.return_value = _chat_returning("I would recommend Pad Thai for them.")
        menu = [MenuItem("Pad Thai", ["GF"])]
        assert llm.find_meal("anything", menu) == "Pad Thai"

    def test_response_contained_in_menu_name(self):
        # LLM returns a shorter form that's a substring of an actual menu name.
        llm.client.chat.return_value = _chat_returning("Karaage")
        menu = [MenuItem("Chicken Karaage ricebowl", ["DF"])]
        assert llm.find_meal("loves chicken", menu) == "Chicken Karaage ricebowl"

    def test_garbage_response_returns_failure_marker(self):
        # No part of "asdfasdf" overlaps any menu name; both substring directions miss.
        llm.client.chat.return_value = _chat_returning("asdfasdf")
        menu = [MenuItem("Mie Goreng", ["V"]), MenuItem("Caesar Salad", ["GF"])]
        assert llm.find_meal("anything", menu) == "LLM FAILURE: incorrect name"

    def test_strips_whitespace_around_response(self):
        llm.client.chat.return_value = _chat_returning("   Caesar Salad\n")
        menu = [MenuItem("Caesar Salad", ["V"])]
        assert llm.find_meal("anything", menu) == "Caesar Salad"

    def test_calls_chat_exactly_once(self):
        llm.client.chat.reset_mock()
        llm.client.chat.return_value = _chat_returning("X")
        llm.find_meal("note", [MenuItem("X", [])])
        assert llm.client.chat.call_count == 1


# --- summarise_feedback ---

class TestSummariseFeedback:
    def test_empty_reviews_returns_canned_string(self):
        assert llm.summarise_feedback([]) == "No feedback available."

    def test_empty_reviews_does_not_call_llm(self):
        llm.client.chat.reset_mock()
        llm.summarise_feedback([])
        assert llm.client.chat.call_count == 0

    def test_returns_llm_output_stripped(self):
        llm.client.chat.return_value = _chat_returning("  Some summary text.  \n")
        result = llm.summarise_feedback([("2026-01-01", "review content")])
        assert result == "Some summary text."

    def test_one_chat_call_per_invocation(self):
        llm.client.chat.reset_mock()
        llm.client.chat.return_value = _chat_returning("summary")
        llm.summarise_feedback([("2026-01-01", "a"), ("2026-01-02", "b"), ("2026-01-03", "c")])
        # Three reviews → still a single LLM call (not per-review).
        assert llm.client.chat.call_count == 1


# --- summarise_feedback_for_caterer ---

class TestSummariseFeedbackForCaterer:
    def test_empty_reviews_returns_empty_string(self):
        # Empty string (not a sentinel) so the caller can omit the section entirely.
        assert llm.summarise_feedback_for_caterer([]) == ""

    def test_empty_reviews_does_not_call_llm(self):
        llm.client.chat.reset_mock()
        llm.summarise_feedback_for_caterer([])
        assert llm.client.chat.call_count == 0

    def test_returns_llm_output_stripped(self):
        llm.client.chat.return_value = _chat_returning("  Balanced recap.  \n")
        result = llm.summarise_feedback_for_caterer([("2026-01-01", "review content")])
        assert result == "Balanced recap."

    def test_one_chat_call_per_invocation(self):
        llm.client.chat.reset_mock()
        llm.client.chat.return_value = _chat_returning("summary")
        llm.summarise_feedback_for_caterer([("2026-01-01", "a"), ("2026-01-02", "b")])
        assert llm.client.chat.call_count == 1


# --- validate_order (LLM judge) ---

class TestValidateOrder:
    MENU = [("Nachos", ["GF"]), ("Pad Thai", [])]

    def test_pass_verdict_returns_ok(self):
        llm.client.chat.return_value = _chat_returning("PASS")
        ok, issues = llm.validate_order("some order", self.MENU, "GYG")
        assert ok is True
        assert issues == []

    def test_fail_verdict_returns_issues(self):
        llm.client.chat.return_value = _chat_returning(
            "FAIL\nDish 'Sushi' is not on the menu.\nNachos quantity is missing."
        )
        ok, issues = llm.validate_order("some order", self.MENU, "GYG")
        assert ok is False
        assert issues == ["Dish 'Sushi' is not on the menu.", "Nachos quantity is missing."]

    def test_fail_with_no_detail_still_flags(self):
        llm.client.chat.return_value = _chat_returning("FAIL")
        ok, issues = llm.validate_order("o", self.MENU, "GYG")
        assert ok is False
        assert issues  # a non-empty placeholder issue

    def test_bullet_prefixes_stripped(self):
        llm.client.chat.return_value = _chat_returning("FAIL\n- Dish off-menu\n* Empty session")
        ok, issues = llm.validate_order("o", self.MENU, "GYG")
        assert ok is False
        assert issues == ["Dish off-menu", "Empty session"]

    def test_empty_output_is_fail_closed(self):
        llm.client.chat.return_value = _chat_returning("   ")
        ok, issues = llm.validate_order("o", self.MENU, "GYG")
        assert ok is False
        assert issues

    def test_unparseable_verdict_is_fail_closed(self):
        llm.client.chat.return_value = _chat_returning("I think it looks fine overall")
        ok, issues = llm.validate_order("o", self.MENU, "GYG")
        assert ok is False
        assert issues

    def test_model_error_is_fail_closed(self):
        llm.client.chat.side_effect = RuntimeError("ollama down")
        ok, issues = llm.validate_order("o", self.MENU, "GYG")
        llm.client.chat.side_effect = None
        assert ok is False
        assert any("could not run" in i for i in issues)


# --- run_model error propagation ---

class TestRunModel:
    def test_propagates_chat_exceptions(self):
        llm.client.chat.side_effect = RuntimeError("ollama down")
        with pytest.raises(RuntimeError, match="ollama down"):
            llm.run_model("hello")
        # Reset for downstream tests so the side_effect doesn't leak.
        llm.client.chat.side_effect = None
