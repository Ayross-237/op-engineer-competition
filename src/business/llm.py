"""Ollama client singleton for local LLM-driven business logic.

On import: pulls the configured model (no-op if already cached) and
pins it in memory so the first real call doesn't pay load latency.
"""
import os
import re
import sys

from dotenv import load_dotenv
from ollama import Client

from src.business.menu import MenuItem

load_dotenv()

host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
client: Client = Client(host=host)

MODEL = "gemma3"

print(f"[llm] Pulling {MODEL} (first-run download may take a few minutes)...", file=sys.stderr)
client.pull(MODEL)

# Empty prompt + keep_alive=-1: loads weights into RAM and never evicts them.
print(f"[llm] Loading {MODEL} into memory...", file=sys.stderr)
client.generate(model=MODEL, keep_alive=-1)
print(f"[llm] {MODEL} ready.", file=sys.stderr)


def run_model(prompt: str) -> str:
    """Run the configured model with the given prompt and return the output."""
    try:
        response = client.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
            keep_alive=-1,
        )
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"Error running model: {e}", file=sys.stderr)
        raise


def find_meal(dietary_extra: str, filtered_menu: list[MenuItem]) -> str:
    """Given a free-text dietary note and a pre-filtered menu of MenuItems
    (already restricted to dishes meeting the student's structured tags),
    pick the single best meal name for that student.
    """
    if not filtered_menu:
        return "NO MEAL AVAILABLE"

    menu_lines = "\n".join(
        f"- {item.name} (tags: {', '.join(item.tags) if item.tags else 'none'})"
        for item in filtered_menu
    )

    prompt = (
        "You are a dietary assistant choosing a meal for a student.\n\n"
        "The following are the dietary tags and their meaning:\n"
        "  GF = gluten-free, DF = dairy-free, NF = nut-free, V = vegetarian, H = halal.\n\n"
        f"Student dietary notes: \"{dietary_extra}\"\n\n"
        "Available menu:\n"
        f"{menu_lines}\n\n"
        "Pick the single meal that BEST satisfies the student's requirements. "
        "Guess which meal would best fit based on the free-text notes "
        "\n"
        "Respond with ONLY the exact meal name from the menu, copied verbatim. "
        "No explanation, no quotes, no extra text."
    )
    raw = run_model(prompt).strip()

    # Validate against the menu — exact match, then substring containment, then fall back.
    menu_names = [item.name for item in filtered_menu]
    if raw in menu_names:
        return raw
    for name in menu_names:
        if name in raw or raw in name:
            return name

    return "LLM FAILURE: incorrect name"

def rank_meals(menu: list[MenuItem], reviews: list[tuple[str, str]]) -> list[MenuItem]:
    """Score every MenuItem in `menu` against the given manager feedback.

    Returns a new list of MenuItems (same name + tags) with `score` populated,
    sorted by score descending. The input items are not mutated.

    Parameters:
    - menu: list of MenuItem to score
    - reviews: list of (date, content) feedback entries about this caterer

    Returns:
    - list of MenuItem with `score` set in [1, 10], sorted high-to-low
    """
    if not menu:
        return []
    if not reviews:
        # Nothing to score against — give every meal a 10 so weighted sampling is uniform.
        return [MenuItem(name=item.name, tags=item.tags, score=10) for item in menu]

    reviews_text = "\n\n".join(f"[{date}]\n{content}" for date, content in reviews)

    scored: list[MenuItem] = []
    for item in menu:
        prompt = (
            f'You are evaluating the dish "{item.name}" based on manager feedback from past weeks.\n\n'
            "Reviews (one per week, newest may be last):\n"
            f"{reviews_text}\n\n"
            f'Based ONLY on what the reviews say about "{item.name}" (ignore comments about other dishes), '
            "give this dish a single integer quality score from 1 to 10 where:\n"
            "  1 = consistently terrible across reviews\n"
            "  5 = mixed, average, or the dish is not mentioned\n"
            "  10 = consistently excellent across reviews\n\n"
            "Respond with ONLY the integer. No words, no punctuation, no explanation.\n"
            "If no reviews mention the dish, give it a 10."
        )
        raw = run_model(prompt).strip()
        scored.append(MenuItem(name=item.name, tags=item.tags, score=_parse_score(raw)))

    scored.sort(key=lambda item: item.score or 0, reverse=True)
    return scored


def _parse_score(raw: str) -> int:
    """Extract an integer in [1, 10] from an LLM response. Falls back to 10 if nothing parses."""
    try:
        n = int(raw.strip())
        if 1 <= n <= 10:
            return n
    except ValueError:
        pass
    # Pick the first standalone 10 or single digit 1-9 anywhere in the response.
    match = re.search(r"\b(10|[1-9])\b", raw)
    if match:
        return int(match.group(1))
    print(f"[llm] rank_meals: could not parse score from {raw!r}, defaulting to 10", file=sys.stderr)
    return 10