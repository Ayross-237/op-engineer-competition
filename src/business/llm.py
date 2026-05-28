"""Ollama client singleton for local LLM-driven business logic.

On import: pulls the configured model (no-op if already cached) and
pins it in memory so the first real call doesn't pay load latency.
"""
import os
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
