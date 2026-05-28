"""Ollama client singleton for local LLM-driven business logic.

On import: pulls the configured model (no-op if already cached) and
pins it in memory so the first real call doesn't pay load latency.
"""
import os
import re
import sys

from dotenv import load_dotenv
from ollama import Client

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


def find_meal(dietary_extra: str, filtered_menu: list[tuple[str, list[str]]]) -> str:
    """Given a list of >= 0 dietary tags and a mandatory dietary_extra string,
    determine which of the meals in the list is most likely to fit the student's needs.

    Parameters:
    - dietary_extra: free-form string with any additional dietary requirements (e.g. "allergic to shellfish")
    - menu: list of (meal name, meal dietary tags) tuples which already fit the student's dietary tags
    """
    if not filtered_menu:
        return "NO MEAL AVAILABLE"

    menu_lines = "\n".join(
        f"- {name} (tags: {', '.join(tags) if tags else 'none'})" for name, tags in filtered_menu
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
    menu_names = [name for name, _ in filtered_menu]
    if raw in menu_names:
        return raw
    for name in menu_names:
        if name in raw or raw in name:
            return name
    
    return "LLM FAILURE: incorrect name"

def rank_meals(menu: list[str], reviews: list[tuple[str, str]]) -> list[tuple[str, int]]:
    """Given a list of meal names and a list of reviews (date, content),
    give each meal a score from 1-10 based on how well it seems to be reviewed.

    Parameters:
    - menu: list of meal names
    - reviews: list of tuples containing (date, content) of reviews

    Returns:
    - list of tuples containing (meal name, score) sorted by score in descending order
    """
    if not menu:
        return []
    if not reviews:
        # Nothing to score against — give every meal a neutral 5.
        return [(name, 5) for name in menu]

    reviews_text = "\n\n".join(f"[{date}]\n{content}" for date, content in reviews)

    scored: list[tuple[str, int]] = []
    for meal in menu:
        prompt = (
            f'You are evaluating the dish "{meal}" based on manager feedback from past weeks.\n\n'
            "Reviews (one per week, newest may be last):\n"
            f"{reviews_text}\n\n"
            f'Based ONLY on what the reviews say about "{meal}" (ignore comments about other dishes), '
            "give this dish a single integer quality score from 1 to 10 where:\n"
            "  1 = consistently terrible across reviews\n"
            "  5 = mixed, average, or the dish is not mentioned\n"
            "  10 = consistently excellent across reviews\n\n"
            "Respond with ONLY the integer. No words, no punctuation, no explanation."
        )
        raw = run_model(prompt).strip()
        scored.append((meal, _parse_score(raw)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def _parse_score(raw: str) -> int:
    """Extract an integer in [1, 10] from an LLM response. Falls back to 5 if nothing parses."""
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
    print(f"[llm] rank_meals: could not parse score from {raw!r}, defaulting to 5", file=sys.stderr)
    return 5