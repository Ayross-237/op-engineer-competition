"""Shared domain type for menu items and date-weighted dish scoring.

`MenuItem` replaces the (name, tags) / (name, tags, score) tuples that used to
flow between helpers, rank_meals and the order-building code. Carrying an
optional `score` on the same shape means downstream callers no longer have to
branch on "is this a ranked menu or a raw one?".

`rank_meals` derives each dish's score from the per-student dish_ratings
collected during past sessions, weighting recent ratings exponentially higher
(replacing the old LLM pass over free-text manager feedback).
"""
import random
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MenuItem:
    name: str
    tags: list[str]
    score: float | None = None

def filter_menu(menu: list[MenuItem], dietary_tags: list[str]) -> list[MenuItem]:
    """Restrict the menu to dishes whose tags are a superset of the student's requirements."""
    requirements = set(dietary_tags)
    return [item for item in menu if requirements.issubset(set(item.tags))]


def pick_dish(student_dietary: list[str], menu: list[MenuItem]) -> str:
    """Pick one matching dish for a student. Weighted by `score` when scores are present
    (defaulting to 1 for any unscored item), so unranked menus degrade to uniform random."""
    filtered = filter_menu(menu, student_dietary)
    if not filtered:
        return f"COULD NOT MATCH ({', '.join(student_dietary)} not met by any dish)"

    weights = [2**item.score - 1 if item.score is not None else 1 for item in filtered]

    return random.choices(filtered, weights=weights, k=1)[0].name


def rank_meals(
    menu: list[MenuItem],
    ratings: list[tuple[str, str, int]],
    half_life_days: float = 21.0,
    default_score: float = 10,
) -> list[MenuItem]:
    """Score each dish by an exponentially date-weighted average of its student ratings.

    Replaces the old LLM pass over free-text manager feedback: each dish gets a score
    in [1, 10] computed from the `dish_ratings` collected during past sessions, with
    more recent ratings weighted exponentially higher. A rating `half_life_days` older
    than the newest rating carries half the weight. Dishes with no ratings fall back to
    `default_score`. Because the per-dish average normalises by its total weight, the
    result depends only on the spread of dates *within* each dish, not the global epoch.

    Parameters:
    - menu: dishes to score (not mutated)
    - ratings: (item_name, date 'YYYY-MM-DD', rating 1-10) tuples for this caterer
    - half_life_days: days-older-than-newest at which a rating's weight halves
    - default_score: score assigned to dishes that have no ratings

    Returns a new list of MenuItems with `score` set, sorted high-to-low.
    """
    if not menu:
        return []

    by_dish: dict[str, list[tuple[datetime, int]]] = {}
    newest: datetime | None = None
    for name, date_str, rating in ratings:
        when = datetime.strptime(date_str, "%Y-%m-%d")
        by_dish.setdefault(name, []).append((when, rating))
        if newest is None or when > newest:
            newest = when

    scored: list[MenuItem] = []
    for item in menu:
        dish = by_dish.get(item.name)
        if not dish:
            score: float = default_score
        else:
            assert newest is not None  # set whenever by_dish is non-empty
            weighted_sum = 0.0
            weight_total = 0.0
            for when, rating in dish:
                weight = 0.5 ** ((newest - when).days / half_life_days)
                weighted_sum += weight * rating
                weight_total += weight
            score = weighted_sum / weight_total
        scored.append(MenuItem(name=item.name, tags=item.tags, score=score))

    scored.sort(key=lambda item: item.score or 10, reverse=True)
    return scored