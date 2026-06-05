"""Generate per-caterer catering orders for the upcoming week and email each caterer.

One order document is produced per caterer (covering every school it serves), with a
requested delivery window per session, and emailed to the caterer's contact (CC'ing the
chef when the caterer opts in).
"""
from pathlib import Path

from src.business import llm
from src.business.email import send_email
from src.business.menu import MenuItem, filter_menu, pick_dish
from src.business.reports import RenderedSession, SessionReport
from src.persistence import helpers
from src.shared.dates import delivery_window
from src.shared.files import markdown_to_pdf, slug


# --- session compute (no markdown) ---

def build_session_report(
    students: list[tuple[int, list[str], str | None]],
    menu: list[MenuItem],
    pricing: tuple[float, float, float],
) -> SessionReport:
    """Crunch a session's roster + menu + pricing into a SessionReport. The only I/O
    here is the per-special-student LLM call inside `find_meal`; no markdown is produced."""
    if not students:
        return SessionReport(student_count=0, pricing=pricing)

    # Free-text dietary requirements route through the LLM one at a time;
    # the rest go through the weighted picker.
    standard = [diet for _, diet, extra in students if not extra]
    special = [(diet, extra) for _, diet, extra in students if extra]

    counts: dict[str, int] = {}
    for diet in standard:
        dish = pick_dish(diet, filter_menu(menu, diet))
        counts[dish] = counts.get(dish, 0) + 1

    assignments: list[tuple[str, str]] = []
    for diet, extra in special:
        req_label = ", ".join([*diet, extra]) if diet else extra
        dish = llm.find_meal(extra, filter_menu(menu, diet))
        assignments.append((req_label, dish))

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
) -> list[RenderedSession]:
    """Compute every scheduled session for a caterer this week, in school then date order.
    build_session_report (non-deterministic: weighted dish sampling + per-student LLM) runs
    exactly once per session here; both output documents render the stored result."""
    sessions: list[RenderedSession] = []
    for school_id, school_name in helpers.get_schools_for_caterer(caterer_id):
        for program_id, day, start, end, dinner, building, mgr_name, mgr_mobile in helpers.get_programs(school_id):
            for session_date, sub_name, sub_mobile in sorted(helpers.get_sessions(program_id, week)):
                catering = helpers.get_students_for_session(program_id, session_date)
                opted_out = helpers.get_students_for_session(program_id, session_date, wants_catering=False)
                sessions.append(RenderedSession(
                    school_name=school_name,
                    header=f"{session_date} ({day} {start}–{end})",
                    building=building,
                    dinner=dinner,
                    manager_line=format_manager_line(mgr_name, mgr_mobile, sub_name, sub_mobile),
                    total_count=len(catering) + len(opted_out),
                    opted_out_count=len(opted_out),
                    report=build_session_report(catering, ranked_menu, pricing),
                ))
    return sessions


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


def build_caterer_order(caterer_name: str, sessions: list[RenderedSession], week: list[str]) -> list[str]:
    """Caterer-facing order document: dishes, dietary notes, delivery window and the
    day-of manager — no internal cost figures or feedback critique."""
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

    return [
        f"# Catering Order — {caterer_name}",
        "",
        f"_Week of {week[0]} – {week[-1]}_",
        "",
        *body,
    ]


def rank_menu_for_caterer(caterer_id: int, feedback: list[tuple[str, str]]) -> list[MenuItem]:
    """Load a caterer's menu and score it once against their feedback."""
    raw_menu = helpers.get_menu(caterer_id)
    menu_items = [MenuItem(name=name, tags=tags) for name, tags in raw_menu]
    return llm.rank_meals(menu_items, feedback)


def write_document(lines: list[str], md_path: Path) -> Path:
    """Write markdown to `md_path`, render the sibling PDF, and return the PDF path."""
    md_path.write_text("\n".join(lines), encoding="utf-8")
    pdf_path = md_path.with_suffix(".pdf")
    markdown_to_pdf(md_path, pdf_path)
    return pdf_path


def dispatch_caterer_order(
    caterer_id: int, caterer_name: str, sessions: list[RenderedSession], week: list[str], output_dir: Path
) -> None:
    """Build the caterer-facing order PDF and email it to the caterer (CC'ing the chef
    when the caterer opts in)."""
    pdf_path = write_document(
        build_caterer_order(caterer_name, sessions, week),
        output_dir / f"orders-{slug(caterer_name)}.md",
    )
    print(f"[orders] {caterer_name}: wrote {pdf_path}")

    contact, chef, cc_chef = helpers.get_caterer_contact(caterer_id)
    cc = [chef] if (cc_chef and chef) else None
    send_email(
        contact,
        f"Padea Catering Order — week of {week[0]}",
        "Please find this week's catering order attached.",
        attachment=str(pdf_path),
        cc=cc,
    )
    print(f"[orders] {caterer_name}: sent to {contact}" + (f" (cc {', '.join(cc)})" if cc else ""))


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
    print(f"[orders] wrote Padea overview {pdf_path}")
    send_email(
        admin_email,
        f"Catering Orders (overview) — week of {week[0]} – {week[-1]}",
        "Please find the combined catering overview attached.",
        attachment=str(pdf_path),
    )


def main(week: list[str], admin_email: str = "aaron.r.dmello@gmail.com") -> None:
    output_dir = Path() / "output"
    output_dir.mkdir(exist_ok=True)

    overview: list[str] = [
        "# Catering Orders (Padea internal)",
        "",
        f"_Week of {week[0]} – {week[-1]}_",
        "",
    ]

    for caterer_id, caterer_name in helpers.get_caterers():
        feedback = helpers.get_feedback(caterer_id)
        ranked_menu = rank_menu_for_caterer(caterer_id, feedback)
        pricing = helpers.get_pricing(caterer_id)

        sessions = compute_caterer_sessions(caterer_id, ranked_menu, pricing, week)
        if not sessions:
            print(f"[orders] {caterer_name}: no sessions this week — skipping")
            continue

        dispatch_caterer_order(caterer_id, caterer_name, sessions, week, output_dir)
        overview += build_overview_section(caterer_name, sessions, feedback)

    send_overview(overview, week, admin_email, output_dir)
