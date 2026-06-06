"""Dev entry point for the student pre-order web app.

Run with:  python -m src.web.run
Requires SUPABASE_URL / SUPABASE_KEY in the environment (.env), and ideally
FLASK_SECRET_KEY set to a random value (a dev default is used otherwise).
"""
from src.web.app import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
