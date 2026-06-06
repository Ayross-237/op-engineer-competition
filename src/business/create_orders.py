"""Generate per-caterer catering orders for the upcoming week and email each caterer.

One order document is produced per caterer (covering every school it serves), with a
requested delivery window per session, and emailed to the caterer's contact (CC'ing the
chef when the caterer opts in).
"""
import logging
from datetime import date, timedelta
from pathlib import Path

from src.business import llm
from src.business.email import send_email
from src.business.menu import MenuItem, filter_menu, pick_dish, rank_meals
from src.business.reports import RenderedSession, SessionReport
from src.persistence import helpers
from src.shared.dates import delivery_window
from src.shared.files import markdown_to_pdf, slug

logger = logging.getLogger("orders")

# Per-student pre-order confirmations are emailed here when the script dispatches the
# orders — NOT to each student's own listed address (keeps students/parents out of the
# loop during the prototype). Edit freely.
CONFIRMATION_RECIPIENT = "aaron.r.dmello@gmail.com"


# --- session compute (no markdown) ---

def build_session_report(
    students: list[tuple[int, list[str], str | None]],
    menu: list[MenuItem],
    pricing: tuple[float, float, float],
    locked_orders: dict[int, str] | None = None,
) -> SessionReport:
    """Crunch a session's roster + menu + pricing into a SessionReport. The only I/O
    here is the per-special-student LLM call inside `find_meal`; no markdown is produced.

    A student in `locked_orders` (student_id -> dish) pre-ordered that meal via the
    web interface, so it is used verbatim and counted as a quantity — overriding both
    the weighted picker and the LLM, and skipping any special-dietary recommendation."""
    if not students:
        return SessionReport(student_count=0, pricing=pricing)

    locked = locked_orders or {}

    # Pre-ordered meals win; otherwise free-text dietary requirements route through the
    # LLM one at a time and the rest go through the weighted picker.
    counts: dict[str, int] = {}
    assignments: list[tuple[str, str]] = []
    for student_id, diet, extra in students:
        if student_id in locked:
            dish = locked[student_id]
            counts[dish] = counts.get(dish, 0) + 1
        elif extra:
            req_label = ", ".join([*diet, extra]) if diet else extra
            dish = llm.find_meal(extra, filter_menu(menu, diet))
            assignments.append((req_label, dish))
        else:
            dish = pick_dish(diet, filter_menu(menu, diet))
            counts[dish] = counts.get(dish, 0) + 1

    per_item, per_trip, per_school = pricing
    # One meal per student, one trip per session, assume one school per trip.
    cost = len(students) * per_item + per_trip + per_school

    return SessionReport(
        student_count=len(students),
        standard_counts=counts,
        special_assignments=assignments,
        cost=cost,
        pricing=pricing,
    )


# --- session render (no compute) ---

def render_session(report: SessionReport, include_cost: bool = False, special_note: bool = False) -> list[str]:
    """Turn a SessionReport into markdown lines for the session body.

    `include_cost` is False for caterer-facing orders (the cost estimate is Padea's
    internal figure); pass True for an internal/admin copy.
    `special_note` appends a caterer instruction under the special-dietary table telling
    them to substitute a suitable dish if a recommendation doesn't fit the student.
    """
    if report.student_count == 0:
        return ["_No catering required._"]

    lines: list[str] = []

    if report.standard_counts:
        lines.append("| Dish | Quantity |")
        lines.append("|------|----------|")
        for dish, qty in sorted(report.standard_counts.items()):
            lines.append(f"| {dish} | {qty} |")

    if report.special_assignments:
        if report.standard_counts:
            lines.append("")
        lines.append("**Special dietary requirements:**")
        lines.append("")
        lines.append("| Dietary Requirements | Recommended Dish |")
        lines.append("|----------------------|------------------|")
        for requirements, dish in report.special_assignments:
            lines.append(f"| {requirements} | {dish} |")
        if special_note:
            lines.append("")
            lines.append(
                "_If a recommended dish does not meet the student's dietary needs, "
                "please substitute another dish from your menu that does._"
            )

    if include_cost:
        per_item, per_trip, per_school = report.pricing
        lines.append("")
        lines.append(
            f"**Estimated cost:** ${report.cost:.2f} "
            f"({report.student_count} × ${per_item:.2f} + ${per_trip:.2f} trip + "
            f"1 × ${per_school:.2f} school fee)"
        )
    return lines


def format_manager_line(
    manager_name: str,
    manager_mobile: str,
    sub_name: str | None,
    sub_mobile: str | None,
) -> str:
    """Render the manager-on-duty line. Sub takes precedence when a sub is named."""
    if sub_name:
        suffix = f" — {sub_mobile}" if sub_mobile else ""
        return f"**Manager (sub for {manager_name}):** {sub_name}{suffix}"
    return f"**Manager:** {manager_name} — {manager_mobile}"


def compute_caterer_sessions(
    caterer_id: int, ranked_menu: list[MenuItem], pricing: tuple[float, float, float], week: list[str]
) -> tuple[list[RenderedSession], list[dict]]:
    """Compute every scheduled session for a caterer this week, in school then date order.
    build_session_report (non-deterministic: weighted dish sampling + per-student LLM) runs
    exactly once per session here; both output documents render the stored result.

    Also returns the pre-orders that made it into the order (locked students who are on
    the catering roster) as confirmation records — these are emailed when the order is
    dispatched. Each record: {student_id, dish, school_name, date, day}."""
    sessions: list[RenderedSession] = []
    confirmations: list[dict] = []
    for school_id, school_name in helpers.get_schools_for_caterer(caterer_id):
        for program_id, day, start, end, dinner, building, mgr_name, mgr_mobile in helpers.get_programs(school_id):
            for session_date, sub_name, sub_mobile in sorted(helpers.get_sessions(program_id, week)):
                catering = helpers.get_students_for_session(program_id, session_date)
                opted_out = helpers.get_students_for_session(program_id, session_date, wants_catering=False)
                locked = helpers.get_meal_orders(program_id, session_date)
                catering_ids = {sid for sid, _, _ in catering}
                pre_ordered = [sid for sid in locked if sid in catering_ids]
                if pre_ordered:
                    logger.info(
                        "%s %s: %d pre-ordered, %d auto-assigned",
                        school_name, session_date, len(pre_ordered), len(catering) - len(pre_ordered),
                    )
                    confirmations += [
                        {"student_id": sid, "dish": locked[sid], "school_name": school_name,
                         "date": session_date, "day": day}
                        for sid in pre_ordered
                    ]
                sessions.append(RenderedSession(
                    school_name=school_name,
                    header=f"{session_date} ({day} {start}–{end})",
                    building=building,
                    dinner=dinner,
                    manager_line=format_manager_line(mgr_name, mgr_mobile, sub_name, sub_mobile),
                    total_count=len(catering) + len(opted_out),
                    opted_out_count=len(opted_out),
                    report=build_session_report(catering, ranked_menu, pricing, locked),
                ))
    return sessions, confirmations


def render_session_block(
    rs: RenderedSession, *, include_cost: bool, include_optout: bool, include_dinner: bool, special_note: bool = False
) -> list[str]:
    """Render one stored session into markdown. Caterer-facing copies hide cost and show a
    plain meal count; the internal overview shows cost and the opted-out breakdown.
    Deterministic — operates only on the already-computed RenderedSession."""
    lines = [
        f"### {rs.header}",
        "",
        f"**Building:** {rs.building}",
        f"**Dinner served at:** {rs.dinner}" if include_dinner else "",
        f"**Requested delivery:** {delivery_window(rs.dinner)}",
        "",
    ]

    if include_optout:
        lines.append(f"**Students:** {rs.total_count} total, {rs.opted_out_count} opted out")
    else:
        lines.append(f"**Meals:** {rs.report.student_count}")

    lines += ["", rs.manager_line, ""]
    lines += render_session(rs.report, include_cost=include_cost, special_note=special_note)
    return lines


def recent_feedback(
    feedback: list[tuple[str, str]], reference_date: date, weeks: int
) -> list[tuple[str, str]]:
    """Filter (submitted_at, content) feedback to entries from the last `weeks` weeks
    up to and including `reference_date`. submitted_at is an ISO-ish timestamp string
    (e.g. '2026-02-24 19:30+10'); unparseable entries are skipped."""
    cutoff = reference_date - timedelta(weeks=weeks)
    out: list[tuple[str, str]] = []
    for submitted_at, content in feedback:
        try:
            submitted = date.fromisoformat(str(submitted_at)[:10])
        except ValueError:
            continue
        if cutoff <= submitted <= reference_date:
            out.append((submitted_at, content))
    return out


def build_caterer_order(
    caterer_name: str,
    sessions: list[RenderedSession],
    week: list[str],
    feedback_summary: str = "",
    feedback_weeks: int = 4,
) -> list[str]:
    """Caterer-facing order document: dishes, dietary notes, delivery window and the
    day-of manager — no internal cost figures. When `feedback_summary` is non-empty it
    is appended as a 'Manager feedback (last N weeks)' section at the bottom."""
    body: list[str] = []
    current_school: str | None = None
    for rs in sessions:
        if rs.school_name != current_school:
            body += [f"## {rs.school_name}", ""]
            current_school = rs.school_name
        body += render_session_block(
            rs, include_cost=False, include_optout=False, include_dinner=False, special_note=True
        )
        body.append("")

    if feedback_summary:
        body += [
            "---",
            "",
            f"## Manager feedback (last {feedback_weeks} weeks)",
            "",
            feedback_summary,
            "",
        ]

    return [
        f"# Catering Order — {caterer_name}",
        "",
        f"_Week of {week[0]} – {week[-1]}_",
        "",
        *body,
    ]


def rank_menu_for_caterer(caterer_id: int) -> list[MenuItem]:
    """Load a caterer's menu and score it once against the per-student dish ratings,
    weighting recent ratings exponentially higher (see menu.rank_meals)."""
    raw_menu = helpers.get_menu(caterer_id)
    menu_items = [MenuItem(name=name, tags=tags) for name, tags in raw_menu]
    ratings = helpers.get_dish_ratings(caterer_id)
    ranked = rank_meals(menu_items, ratings)

    logger.info("Ranked %d dishes from %d student ratings:", len(ranked), len(ratings))
    for item in ranked:
        logger.info("    %5.2f  %s", item.score if item.score is not None else 0.0, item.name)
    return ranked


def write_document(lines: list[str], md_path: Path) -> Path:
    """Write markdown to `md_path`, render the sibling PDF, and return the PDF path."""
    md_path.write_text("\n".join(lines), encoding="utf-8")
    pdf_path = md_path.with_suffix(".pdf")
    markdown_to_pdf(md_path, pdf_path)
    return pdf_path


def send_pre_order_confirmations(caterer_name: str, confirmations: list[dict]) -> None:
    """Email a confirmation for each student pre-order included in the dispatched order.

    Sent to CONFIRMATION_RECIPIENT (never the student's own address). Best-effort: a
    mail failure is logged and skipped so it can't abort the order run. Student names
    are looked up once each and cached across the caterer's confirmations."""
    if not confirmations:
        return
    names: dict[int, str] = {}
    sent = 0
    for c in confirmations:
        sid = c["student_id"]
        if sid not in names:
            names[sid] = helpers.get_student_name(sid)
        subject = f"Meal pre-order confirmed — {c['dish']} ({c['date']})"
        body = (
            f"Hi {names[sid]},\n\n"
            f"Your pre-ordered meal has been placed with {caterer_name}:\n\n"
            f"  Dish:    {c['dish']}\n"
            f"  School:  {c['school_name']}\n"
            f"  Session: {c['date']} ({c['day']})\n\n"
            "If this isn't right, please let your program manager know.\n"
        )
        try:
            send_email(CONFIRMATION_RECIPIENT, subject, body)
            sent += 1
        except Exception:
            logger.warning("Pre-order confirmation failed for %s (%s)", names[sid], c["dish"], exc_info=True)
        break # Here for testing to speed up runs and avoid spamming the inbox; remove to send all confirmations.
    # Using an placeholder email to avoid sending to unknown addresses.
    logger.info("%s: sent %d pre-order confirmation(s) to %s", caterer_name, sent, CONFIRMATION_RECIPIENT)


def dispatch_caterer_order(
    caterer_id: int,
    caterer_name: str,
    order_lines: list[str],
    week: list[str],
    output_dir: Path,
) -> None:
    """Write the (already-built and validated) caterer order PDF and email it to the
    caterer (CC'ing the chef when the caterer opts in)."""
    pdf_path = write_document(
        order_lines,
        output_dir / f"orders-{slug(caterer_name)}.md",
    )
    logger.info("%s: wrote order PDF %s", caterer_name, pdf_path)

    contact, chef, cc_chef = helpers.get_caterer_contact(caterer_id)
    cc = [chef] if (cc_chef and chef) else None
    send_email(
        contact,
        f"Padea Catering Order — week of {week[0]}",
        "Please find this week's catering order attached.",
        attachment=str(pdf_path),
        cc=cc,
    )
    logger.info("%s: emailed order to %s%s", caterer_name, contact, f" (cc {', '.join(cc)})" if cc else "")


def build_overview_section(
    caterer_name: str, sessions: list[RenderedSession], feedback: list[tuple[str, str]]
) -> list[str]:
    """Internal overview markdown for one caterer: every session with cost + opt-out
    breakdown, followed by the LLM feedback summary."""
    lines = [f"## {caterer_name}", ""]
    current_school: str | None = None
    for rs in sessions:
        if rs.school_name != current_school:
            lines += [f"### {rs.school_name}", ""]
            current_school = rs.school_name
        lines += render_session_block(rs, include_cost=True, include_optout=True, include_dinner=True)
        lines.append("")
    lines += ["**Caterer feedback summary:**", "", llm.summarise_feedback(feedback), ""]
    return lines


def send_overview(overview: list[str], week: list[str], admin_email: str, output_dir: Path) -> None:
    """Write the combined Padea overview PDF and email it to the admin."""
    pdf_path = write_document(overview, output_dir / "orders.md")
    logger.info("Wrote Padea overview PDF %s", pdf_path)
    send_email(
        admin_email,
        f"Catering Orders (overview) — week of {week[0]} – {week[-1]}",
        "Please find the combined catering overview attached.",
        attachment=str(pdf_path),
    )
    logger.info("Emailed overview to %s", admin_email)


def email_validation_failure(admin_email: str, failures: dict[str, list[str]], week: list[str]) -> None:
    """Email the admin a combined report when the LLM judge rejects one or more orders.
    Validation is all-or-nothing, so when this fires NOTHING was sent to any caterer."""
    lines = [
        f"Catering order validation FAILED for the week of {week[0]} - {week[-1]}.",
        "",
        "No orders were sent to any caterer. The LLM judge flagged the following:",
        "",
    ]
    for caterer_name, issues in failures.items():
        lines.append(f"{caterer_name}:")
        lines += [f"  - {issue}" for issue in issues]
        lines.append("")
    lines.append("Review the generated orders in output/, fix the cause, and re-run.")
    send_email(admin_email, f"[ACTION NEEDED] Catering orders held — validation failed ({week[0]})", "\n".join(lines))
    logger.info("Emailed validation-failure report to %s", admin_email)


def main(
    week: list[str],
    admin_email: str = "aaron.r.dmello@gmail.com",
    feedback_weeks: int = 5,
    feedback_reference: date | None = None,
) -> None:
    # Configure logging if the caller hasn't already (no-op when handlers exist),
    # so running the pipeline directly still surfaces the stage-by-stage progress.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quieten the HTTP client chatter (httpx/httpcore back supabase and ollama,
    # urllib3 backs requests) so the per-request lines don't drown the stages.
    for noisy in ("httpx", "httpcore", "urllib3", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    output_dir = Path() / "output"
    output_dir.mkdir(exist_ok=True)
    reference = feedback_reference or date.today()
    logger.info("Generating catering orders for week %s - %s", week[0], week[-1])

    overview: list[str] = [
        "# Catering Orders (Padea internal)",
        "",
        f"_Week of {week[0]} – {week[-1]}_",
        "",
    ]
    prepared: list[dict] = []  # built-but-not-yet-sent orders, validated as a batch below

    caterers = helpers.get_caterers()
    logger.info("Processing %d caterer(s)", len(caterers))

    for caterer_id, caterer_name in caterers:
        logger.info("--- %s (id=%d) ---", caterer_name, caterer_id)

        feedback = helpers.get_feedback(caterer_id)
        logger.info("%s: loaded %d feedback entr%s", caterer_name, len(feedback), "y" if len(feedback) == 1 else "ies")

        recent = recent_feedback(feedback, reference, feedback_weeks)
        caterer_summary = llm.summarise_feedback_for_caterer(recent) if recent else ""
        logger.info("%s: %d feedback entr%s in the last %d weeks", caterer_name,
                    len(recent), "y" if len(recent) == 1 else "ies", feedback_weeks)

        ranked_menu = rank_menu_for_caterer(caterer_id)

        pricing = helpers.get_pricing(caterer_id)
        logger.info("%s: pricing $%.2f/item, $%.2f/trip, $%.2f/school", caterer_name, *pricing)

        logger.info("%s: computing sessions for the week...", caterer_name)
        sessions, pre_orders = compute_caterer_sessions(caterer_id, ranked_menu, pricing, week)
        if not sessions:
            logger.info("%s: no sessions this week — skipping", caterer_name)
            continue
        logger.info("%s: computed %d session(s)", caterer_name, len(sessions))

        order_lines = build_caterer_order(caterer_name, sessions, week, caterer_summary, feedback_weeks)
        prepared.append({
            "caterer_id": caterer_id,
            "caterer_name": caterer_name,
            "order_lines": order_lines,
            "pre_orders": pre_orders,
            "menu": [(item.name, item.tags) for item in ranked_menu],
        })
        overview += build_overview_section(caterer_name, sessions, feedback)

    # --- LLM-as-judge: validate every order BEFORE anything is sent (all-or-nothing) ---
    logger.info("Validating %d order(s) with the LLM judge before sending...", len(prepared))
    failures: dict[str, list[str]] = {}
    for p in prepared:
        ok, issues = llm.validate_order("\n".join(p["order_lines"]), p["menu"], p["caterer_name"])
        if ok:
            logger.info("%s: order passed validation", p["caterer_name"])
        else:
            failures[p["caterer_name"]] = issues
            logger.error("%s: order FAILED validation — %s", p["caterer_name"], "; ".join(issues))

    if failures:
        logger.error("Validation failed for %d of %d order(s); holding ALL orders.", len(failures), len(prepared))
        email_validation_failure(admin_email, failures, week)
        return

    # --- all clear: dispatch every order, send confirmations, then the internal overview ---
    for p in prepared:
        dispatch_caterer_order(p["caterer_id"], p["caterer_name"], p["order_lines"], week, output_dir)
        send_pre_order_confirmations(p["caterer_name"], p["pre_orders"])

    logger.info("Assembling and sending the Padea overview...")
    send_overview(overview, week, admin_email, output_dir)
    logger.info("Done - all caterer orders sent for week %s - %s", week[0], week[-1])
