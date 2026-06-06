"""Ollama client singleton for local LLM-driven business logic.

On import: pulls the configured model (no-op if already cached) and
pins it in memory so the first real call doesn't pay load latency.
"""
import os
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


def summarise_feedback(reviews: list[tuple[str, str]]) -> str:
    """Generate a concise summary of the manager feedback for this caterer."""
    if not reviews:
        return "No feedback available."

    reviews_text = "\n\n".join(f"[{date}]\n{content}" for date, content in reviews)
    prompt = (
        "You are a helpful assistant summarising catering manager feedback for the upcoming week's orders.\n\n"
        "Summarise the following feedback into a concise overview of the caterer's strengths and weaknesses, "
        "focusing on actionable insights about the food quality, reliability, and suitability for students:\n\n"
        f"{reviews_text}\n\n"
        "Respond with a brief summary in 2-3 sentences. This is aimed at the program manager and administrator."
        "This should be short and concise, focussed on strengths a weakness of the caterer and dishes"
        "Only include the actual review and no headers or extraneous text."
    )
    return run_model(prompt).strip()


def summarise_feedback_for_caterer(reviews: list[tuple[str, str]], target_words: int = 300) -> str:
    """Summarise manager feedback into a caterer-facing recap of about `target_words`
    words, for appending to the caterer's order.

    Tone is factual and neutral: a balanced account of what went well and what fell
    short, naming specific dishes, with no praise or scolding. Returns "" for no reviews
    (the caller omits the section rather than printing an empty heading)."""
    if not reviews:
        return ""

    reviews_text = "\n\n".join(f"[{date}]\n{content}" for date, content in reviews)
    prompt = (
        "You are summarising catering manager feedback to share directly with the caterer.\n\n"
        "Feedback entries (one per session, newest last):\n"
        f"{reviews_text}\n\n"
        f"Write a balanced, factual summary of about {target_words} words covering both what "
        "worked well and what fell short, referring to specific dishes where the feedback does. "
        "Keep a neutral, professional tone — neither praising nor scolding — an accurate recap "
        "the caterer can act on. Do not invent details not present in the feedback. "
        "Respond with prose only: no headings, no bullet points, no preamble."
        "DO NOT include any header or extraneous text — just the summary itself, suitable for appending to the caterer's order."
    )
    return run_model(prompt).strip()


def validate_order(order_text: str, menu: list[tuple[str, list[str]]], caterer_name: str) -> tuple[bool, list[str]]:
    """LLM-as-judge check of a generated caterer order before it is sent.

    Returns (ok, issues): ok=True with no issues when the order looks correct, else
    ok=False with one short sentence per problem. Fail-closed — if the model errors or
    its verdict can't be parsed, returns (False, [...]) so the caller holds the order.
    """
    menu_lines = "\n".join(
        f"- {name} (tags: {', '.join(tags) if tags else 'none'})" for name, tags in menu
    )
    prompt = (
        "You are a quality checker reviewing a school catering order before it is "
        f"emailed to the caterer '{caterer_name}'. Be precise; only flag real problems.\n\n"
        "The generated order:\n"
        "-----\n"
        f"{order_text}\n"
        "-----\n\n"
        "Flag ONLY the following issues, if present:\n"
        " - The order is obviously malformed of incomplete."
        "Respond in EXACTLY this format and nothing else:\n"
        "First line: PASS or FAIL\n"
        "If FAIL, each following line is one short sentence describing one problem."
    )
    try:
        raw = run_model(prompt).strip()
    except Exception as e:
        return False, [f"validation could not run: {e}"]

    lines = [ln.strip("-* \t") for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return False, ["validator returned no output"]
    verdict = lines[0].upper()
    if verdict.startswith("PASS"):
        return True, []
    if verdict.startswith("FAIL"):
        return False, lines[1:] or ["unspecified problem reported"]
    return False, [f"could not parse validator verdict: {raw[:200]}"]