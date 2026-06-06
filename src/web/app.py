"""Student pre-order web app.

A small Flask front end that lets a student lock in a specific dish for an upcoming
session ahead of time. A locked order is honoured verbatim by the order generator
(create_orders.build_session_report); students who don't pre-order are auto-assigned
from the weighted dish ranking as before.

Auth is deliberately minimal for this prototype: a student logs in with just their
school email (no password) and we keep their id in the Flask session. There is no
ordering cutoff — a pre-order can be set or changed until the admin runs the generator.
"""
import functools
import os

from flask import Flask, flash, redirect, render_template, request, session, url_for

from src.business.menu import MenuItem, filter_menu
from src.persistence import helpers


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def _find_session(student_id: int, program_id: int, date: str) -> dict | None:
    """Return the student's session matching (program_id, date), or None.

    Looking the session up in the student's own upcoming list is the authorisation
    check: it confirms the student is enrolled, not absent, and the session exists —
    and it yields the server-trusted caterer_id (never taken from the request)."""
    for s in helpers.get_upcoming_sessions_for_student(student_id):
        if s["program_id"] == program_id and s["date"] == date:
            return s
    return None


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-insecure-key")

    @app.route("/")
    def index():
        if session.get("student_id"):
            return redirect(url_for("sessions"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip()
            student = helpers.get_student_by_email(email)
            if not student:
                flash("No student found with that email.", "error")
                return render_template("login.html", email=email)
            sid, name, dietary, dietary_extra = student
            session.clear()
            session["student_id"] = sid
            session["student_name"] = name
            session["dietary"] = dietary
            session["dietary_extra"] = dietary_extra
            return redirect(url_for("sessions"))
        return render_template("login.html", email="")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/sessions")
    @login_required
    def sessions():
        student_id = session["student_id"]
        upcoming = helpers.get_upcoming_sessions_for_student(student_id)
        for s in upcoming:
            s["order"] = helpers.get_meal_order(student_id, s["program_id"], s["date"])
        return render_template(
            "sessions.html",
            sessions=upcoming,
            student_name=session.get("student_name"),
        )

    @app.route("/sessions/<int:program_id>/<date>", methods=["GET", "POST"])
    @login_required
    def order(program_id: int, date: str):
        student_id = session["student_id"]
        sess = _find_session(student_id, program_id, date)
        if sess is None:
            flash("That session isn't available for you to order.", "error")
            return redirect(url_for("sessions"))

        dietary = session.get("dietary") or []
        raw_menu = helpers.get_menu(sess["caterer_id"])
        choices = filter_menu([MenuItem(name=n, tags=t) for n, t in raw_menu], dietary)

        if request.method == "POST":
            action = request.form.get("action")
            if action == "clear":
                helpers.delete_meal_order(student_id, program_id, date)
                flash("Pre-order cleared — your meal will be auto-assigned.", "success")
                return redirect(url_for("sessions"))

            item_name = request.form.get("item_name")
            allowed = {item.name for item in choices}
            if item_name not in allowed:
                flash("Please choose a dish from your menu.", "error")
            else:
                helpers.upsert_meal_order(student_id, program_id, date, sess["caterer_id"], item_name)
                flash(f"Locked in: {item_name}", "success")
                return redirect(url_for("sessions"))

        current = helpers.get_meal_order(student_id, program_id, date)
        return render_template(
            "order.html",
            session=sess,
            choices=choices,
            current=current,
            dietary=dietary,
            dietary_extra=session.get("dietary_extra"),
        )

    return app


app = create_app()
