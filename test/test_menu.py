"""Tests for src.business.menu.

Covers MenuItem construction defaults, filter_menu's subset semantics,
and pick_dish's weighted-random behaviour (with and without scores).
"""
import random
from collections import Counter

import pytest

from src.business.menu import MenuItem, filter_menu, pick_dish, rank_meals


# --- MenuItem ---

class TestMenuItem:
    def test_minimal_construction(self):
        item = MenuItem(name="Pad Thai", tags=["GF"])
        assert item.name == "Pad Thai"
        assert item.tags == ["GF"]
        assert item.score is None

    def test_with_score(self):
        item = MenuItem(name="Pad Thai", tags=["GF"], score=8)
        assert item.score == 8

    def test_empty_tags_allowed(self):
        item = MenuItem(name="Plain Rice", tags=[])
        assert item.tags == []


# --- filter_menu ---

class TestFilterMenu:
    def test_empty_menu_returns_empty(self):
        assert filter_menu([], ["GF"]) == []

    def test_empty_requirements_returns_all(self):
        menu = [MenuItem("a", ["GF"]), MenuItem("b", []), MenuItem("c", ["V"])]
        assert filter_menu(menu, []) == menu

    def test_subset_matches(self):
        menu = [
            MenuItem("strict", ["GF", "DF", "NF"]),
            MenuItem("looser", ["GF"]),
            MenuItem("none", []),
        ]
        # Requiring GF only — both strict and looser qualify.
        result = filter_menu(menu, ["GF"])
        assert [item.name for item in result] == ["strict", "looser"]

    def test_no_items_match(self):
        menu = [MenuItem("a", ["GF"]), MenuItem("b", ["V"])]
        assert filter_menu(menu, ["H"]) == []

    def test_multiple_requirements_all_must_be_present(self):
        menu = [
            MenuItem("has_both", ["GF", "DF"]),
            MenuItem("only_gf", ["GF"]),
            MenuItem("only_df", ["DF"]),
        ]
        result = filter_menu(menu, ["GF", "DF"])
        assert [item.name for item in result] == ["has_both"]

    def test_tag_order_doesnt_matter(self):
        menu = [MenuItem("a", ["DF", "GF"])]
        # filter uses set semantics, so requirement order is irrelevant.
        assert filter_menu(menu, ["GF", "DF"]) == menu

    def test_preserves_menu_order(self):
        menu = [MenuItem(name, ["GF"]) for name in ("z", "a", "m", "q")]
        result = filter_menu(menu, ["GF"])
        assert [item.name for item in result] == ["z", "a", "m", "q"]


# --- pick_dish ---

class TestPickDish:
    def test_no_matches_returns_failure_marker(self):
        menu = [MenuItem("a", ["GF"]), MenuItem("b", ["V"])]
        result = pick_dish(["H"], menu)
        assert result.startswith("COULD NOT MATCH")
        assert "H" in result

    def test_no_matches_marker_lists_all_unmet_tags(self):
        result = pick_dish(["GF", "H"], [])
        # Both tags should appear in the diagnostic.
        assert "GF" in result and "H" in result

    def test_single_match_always_returned(self):
        menu = [MenuItem("only", ["GF"], score=5), MenuItem("other", ["V"], score=99)]
        # Only "only" matches; deterministic regardless of score weight.
        assert pick_dish(["GF"], menu) == "only"

    def test_weighted_distribution_favours_high_scores(self):
        menu = [
            MenuItem("rare", ["GF"], score=1),
            MenuItem("common", ["GF"], score=99),
        ]
        samples = [pick_dish(["GF"], menu) for _ in range(1000)]
        counts = Counter(samples)
        # With 99:1 weighting, "common" should overwhelmingly dominate.
        assert counts["common"] > 900
        assert counts["rare"] > 0  # but rare still gets a few

    def test_no_scores_is_uniform(self):
        menu = [MenuItem("a", []), MenuItem("b", []), MenuItem("c", [])]
        samples = [pick_dish([], menu) for _ in range(3000)]
        counts = Counter(samples)
        # Each item weight defaults to 1 → ~33% each. Allow wide tolerance.
        for name in ("a", "b", "c"):
            assert 800 < counts[name] < 1200

    def test_mixed_scores_and_none_treats_none_as_one(self):
        menu = [
            MenuItem("scored_high", [], score=10),
            MenuItem("unscored", [], score=None),
        ]
        samples = [pick_dish([], menu) for _ in range(1100)]
        counts = Counter(samples)
        # weights = [10, 1] → ~10:1 ratio. scored_high should be ~1000, unscored ~100.
        assert counts["scored_high"] > counts["unscored"] * 5

    def test_zero_score_item_never_picked(self):
        menu = [MenuItem("never", [], score=0), MenuItem("always", [], score=10)]
        samples = [pick_dish([], menu) for _ in range(500)]
        print(samples)
        assert "never" not in samples

    def test_picks_only_from_filtered_subset(self):
        """An item that doesn't satisfy the dietary tags must never be returned,
        no matter how high its score is."""
        menu = [
            MenuItem("not_gf_but_huge", [], score=1000),
            MenuItem("gf_small", ["GF"], score=1),
        ]
        samples = [pick_dish(["GF"], menu) for _ in range(50)]
        assert set(samples) == {"gf_small"}

    def test_deterministic_under_seeded_random(self):
        menu = [MenuItem("a", [], score=1), MenuItem("b", [], score=1)]
        # The autouse conftest fixture seeds random for each test; we further
        # reseed inside the test to be explicit about determinism.
        random.seed(42)
        first = [pick_dish([], menu) for _ in range(20)]
        random.seed(42)
        second = [pick_dish([], menu) for _ in range(20)]
        assert first == second


# --- rank_meals ---

class TestRankMeals:
    def test_empty_menu_returns_empty(self):
        assert rank_meals([], [("a", "2026-01-01", 8)]) == []

    def test_no_ratings_assigns_default_score(self):
        menu = [MenuItem("a", ["GF"]), MenuItem("b", [])]
        ranked = rank_meals(menu, [], default_score=5.0)
        assert len(ranked) == 2
        assert all(item.score == 5.0 for item in ranked)

    def test_dish_with_no_ratings_uses_default(self):
        # "b" has no ratings → falls back to default; "a" averages its ratings.
        menu = [MenuItem("a", []), MenuItem("b", [])]
        ranked = {i.name: i.score for i in rank_meals(menu, [("a", "2026-01-01", 9)], default_score=5.0)}
        assert ranked["a"] == 9.0
        assert ranked["b"] == 5.0

    def test_single_rating_equals_that_rating(self):
        ranked = rank_meals([MenuItem("a", [])], [("a", "2026-01-01", 7)])
        assert ranked[0].score == 7.0

    def test_equal_dates_give_plain_mean(self):
        # Same date → equal weights → arithmetic mean of 4 and 8 = 6.
        ratings = [("a", "2026-01-01", 4), ("a", "2026-01-01", 8)]
        assert rank_meals([MenuItem("a", [])], ratings)[0].score == 6.0

    def test_recent_ratings_weighted_higher(self):
        # Old low score, recent high score: weighted average must beat the plain mean (5.5).
        ratings = [("a", "2026-01-01", 1), ("a", "2026-03-01", 10)]
        score = rank_meals([MenuItem("a", [])], ratings, half_life_days=21.0)[0].score
        assert score > 5.5
        assert score < 10.0

    def test_half_life_controls_recency_bias(self):
        # A shorter half-life weights the recent high rating even more heavily.
        ratings = [("a", "2026-01-01", 1), ("a", "2026-03-01", 10)]
        short = rank_meals([MenuItem("a", [])], ratings, half_life_days=7.0)[0].score
        long = rank_meals([MenuItem("a", [])], ratings, half_life_days=60.0)[0].score
        assert short > long

    def test_result_independent_of_global_epoch(self):
        # Shifting every date by the same offset (preserving the within-dish gap)
        # must not change the score — per-dish normalisation cancels the epoch.
        # Both pairs span the same 14-day gap.
        a = rank_meals([MenuItem("a", [])], [("a", "2026-01-01", 3), ("a", "2026-01-15", 9)])[0].score
        b = rank_meals([MenuItem("a", [])], [("a", "2026-06-01", 3), ("a", "2026-06-15", 9)])[0].score
        assert a == pytest.approx(b)

    def test_returns_sorted_descending_by_score(self):
        menu = [MenuItem("a", []), MenuItem("b", []), MenuItem("c", [])]
        ratings = [("a", "2026-01-01", 3), ("b", "2026-01-01", 9), ("c", "2026-01-01", 6)]
        ranked = rank_meals(menu, ratings)
        assert [i.name for i in ranked] == ["b", "c", "a"]
        scores = [i.score for i in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_input_items_are_not_mutated(self):
        menu = [MenuItem("a", ["GF"]), MenuItem("b", ["V"])]
        rank_meals(menu, [("a", "2026-01-01", 3), ("b", "2026-01-01", 9)])
        assert menu[0].score is None
        assert menu[1].score is None

    def test_tags_preserved_in_returned_items(self):
        ranked = rank_meals([MenuItem("a", ["GF", "DF"])], [("a", "2026-01-01", 7)])
        assert ranked[0].tags == ["GF", "DF"]

    def test_ratings_for_unknown_dishes_ignored(self):
        # A rating for a dish not on the menu must not appear in the output.
        ranked = rank_meals([MenuItem("a", [])], [("ghost", "2026-01-01", 10)], default_score=5.0)
        assert [i.name for i in ranked] == ["a"]
        assert ranked[0].score == 5.0
