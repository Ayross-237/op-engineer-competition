"""Shared domain type for menu items.

`MenuItem` replaces the (name, tags) / (name, tags, score) tuples that used to
flow between helpers, llm.rank_meals and the order-building code. Carrying an
optional `score` on the same shape means downstream callers no longer have to
branch on "is this a ranked menu or a raw one?".
"""
import random
from dataclasses import dataclass

@dataclass
class MenuItem:
    name: str
    tags: list[str]
    score: int | None = None

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
    weights = [item.score if item.score is not None else 1 for item in filtered]
    return random.choices(filtered, weights=weights, k=1)[0].name