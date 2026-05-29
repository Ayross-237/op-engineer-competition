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


# --- _parse_score (pure) ---

class TestParseScore:
    def test_bare_integer_in_range(self):
        for n in range(1, 11):
            assert llm._parse_score(str(n)) == n

    def test_zero_falls_to_regex_path(self):
        # "0" parses as int but is out-of-range → regex looks for [1-9]/10.
        # "0" has no digit 1-9, so it falls all the way to the default 10.
        assert llm._parse_score("0") == 10

    def test_eleven_falls_through_to_default(self):
        # int("11") = 11, out of range → regex needs word boundaries on both sides
        # of the digit. "11" has no internal \b, so neither "10" nor "1" matches.
        # Defaults to 10.
        assert llm._parse_score("11") == 10

    def test_strips_whitespace(self):
        assert llm._parse_score("   7   ") == 7
        assert llm._parse_score("\n\t8\n") == 8

    def test_regex_falls_back_to_first_in_range_digit(self):
        assert llm._parse_score("I think the score is 7 out of 10") == 7
        assert llm._parse_score("Rating: 4") == 4

    def test_regex_prefers_10_over_single_digit(self):
        # \b(10|[1-9])\b — order of alternatives means 10 wins when present at start.
        assert llm._parse_score("10") == 10

    def test_nothing_parseable_defaults_to_ten(self):
        assert llm._parse_score("no idea") == 10
        assert llm._parse_score("") == 10

    def test_negative_number_uses_absolute_digit(self):
        # "-3" has int parse fail (the minus makes it parse as negative, in range it'd be -3 → reject),
        # but regex \b3\b matches the bare 3 in the string. Result: 3.
        assert llm._parse_score("-3") == 3


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


# --- rank_meals ---

class TestRankMeals:
    def test_empty_menu_returns_empty(self):
        assert llm.rank_meals([], [("2026-01-01", "anything")]) == []

    def test_no_reviews_assigns_score_ten(self):
        menu = [MenuItem("a", ["GF"]), MenuItem("b", [])]
        ranked = llm.rank_meals(menu, [])
        assert len(ranked) == 2
        assert all(item.score == 10 for item in ranked)

    def test_no_reviews_does_not_call_llm(self):
        llm.client.chat.reset_mock()
        llm.rank_meals([MenuItem("a", [])], [])
        assert llm.client.chat.call_count == 0

    def test_one_chat_call_per_menu_item(self):
        llm.client.chat.reset_mock()
        llm.client.chat.return_value = _chat_returning("7")
        menu = [MenuItem(f"item{i}", []) for i in range(4)]
        llm.rank_meals(menu, [("2026-01-01", "some review")])
        assert llm.client.chat.call_count == 4

    def test_returns_sorted_descending_by_score(self):
        # Sequentially return descending scores; result should be re-sorted high→low
        # (and stay that way even though we returned them in input order).
        llm.client.chat.side_effect = [
            _chat_returning("3"),
            _chat_returning("9"),
            _chat_returning("6"),
        ]
        menu = [MenuItem("a", []), MenuItem("b", []), MenuItem("c", [])]
        ranked = llm.rank_meals(menu, [("2026-01-01", "review")])
        scores = [item.score for item in ranked]
        assert scores == sorted(scores, reverse=True)
        assert ranked[0].name == "b"  # was assigned 9

    def test_input_items_are_not_mutated(self):
        menu = [MenuItem("a", ["GF"]), MenuItem("b", ["V"])]
        llm.client.chat.side_effect = [_chat_returning("3"), _chat_returning("9")]
        llm.rank_meals(menu, [("2026-01-01", "review")])
        # Original items still have score=None.
        assert menu[0].score is None
        assert menu[1].score is None

    def test_tags_preserved_in_returned_items(self):
        llm.client.chat.return_value = _chat_returning("7")
        menu = [MenuItem("a", ["GF", "DF"])]
        ranked = llm.rank_meals(menu, [("2026-01-01", "review")])
        assert ranked[0].tags == ["GF", "DF"]

    def test_garbage_llm_response_defaults_to_ten(self):
        llm.client.chat.return_value = _chat_returning("no idea what to say")
        menu = [MenuItem("a", [])]
        ranked = llm.rank_meals(menu, [("2026-01-01", "review")])
        # _parse_score returns 10 when nothing parses.
        assert ranked[0].score == 10


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


# --- run_model error propagation ---

class TestRunModel:
    def test_propagates_chat_exceptions(self):
        llm.client.chat.side_effect = RuntimeError("ollama down")
        with pytest.raises(RuntimeError, match="ollama down"):
            llm.run_model("hello")
        # Reset for downstream tests so the side_effect doesn't leak.
        llm.client.chat.side_effect = None
