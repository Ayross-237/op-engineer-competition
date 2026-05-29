"""Generate per-session catering orders for the upcoming week as a markdown file."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from src.business import llm
from src.business.email import send_email
from src.business.menu import MenuItem, filter_menu, pick_dish
from src.persistence import helpers
from src.shared.dates import next_week


# --- domain types ---

@dataclass
class SessionReport:
    """The fully-computed view of one session, ready for rendering."""
    student_count: int
    standard_counts: dict[str, int] = field(default_factory=dict)
    special_assignments: list[tuple[str, str]] = field(default_factory=list)  # (requirements label, dish)
    cost: float = 0.0
    pricing: tuple[float, float, float] = (0.0, 0.0, 0.0)


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

def render_session(report: SessionReport) -> list[str]:
    """Turn a SessionReport into markdown lines for the session body."""
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


def markdown_to_pdf(md_path: Path, pdf_path: Path) -> None:
    from markdown_pdf import MarkdownPdf, Section

    css = (
        "table { border-collapse: collapse; margin: 8px 0; }"
        "th, td { border: 1px solid #888; padding: 4px 8px; }"
    )
    pdf = MarkdownPdf()
    pdf.add_section(Section(md_path.read_text(encoding="utf-8")), user_css=css)
    pdf.save(str(pdf_path))


def main(week: list[str]) -> None:
    sections: list[str] = [
        "# Catering Orders",
        "",
        f"_Week of {week[0]} – {week[-1]}_",
        "",
    ]

    for school_id, school_name in helpers.get_schools():
        sections.append(f"## {school_name}")
        sections.append("")

        caterer_id = helpers.get_caterer(school_id)
        caterer_name = helpers.get_caterer_name(caterer_id)
        pricing = helpers.get_pricing(caterer_id)
        programs = helpers.get_programs(school_id)

        # Convert raw menu rows into MenuItems and score them once per school
        # (the LLM ranking is the same for every session at this school).
        raw_menu = helpers.get_menu(caterer_id)
        menu_items = [MenuItem(name=name, tags=tags) for name, tags in raw_menu]
        ranked_menu = llm.rank_meals(menu_items, helpers.get_feedback(caterer_id))

        session_printed = False
        for program_id, day, start, end, dinner, mgr_name, mgr_mobile in programs:
            session_rows = helpers.get_sessions(program_id, week)
            for session_date, sub_name, sub_mobile in sorted(session_rows):
                session_printed = True
                catering = helpers.get_students_for_session(program_id, session_date)
                opted_out = helpers.get_students_for_session(program_id, session_date, wants_catering=False)
                total_count = len(catering) + len(opted_out)
                sections.append(f"### {session_date} ({day} {start}–{end}): {caterer_name}")
                sections.append("")
                sections.append(f"**Dinner served at:** {dinner}")
                sections.append("")
                sections.append(f"**Students:** {total_count} total, {len(opted_out)} opted out")
                sections.append("")
                sections.append(format_manager_line(mgr_name, mgr_mobile, sub_name, sub_mobile))
                sections.append("")
                report = build_session_report(catering, ranked_menu, pricing)
                sections.extend(render_session(report))

        if not session_printed:
            sections.append("_No sessions scheduled this week._")
            sections.append("")
        else:
            sections.append("### Caterer feedback summary:")
            sections.append(llm.summarise_feedback(helpers.get_feedback(caterer_id)))
            sections.append("")

    output = Path() / "output" / "orders.md"
    output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Wrote {output}")

    pdf_output = output.with_suffix(".pdf")
    markdown_to_pdf(output, pdf_output)
    print(f"Wrote {pdf_output}")
    send_email(
        "aaron.r.dmello@gmail.com",
        f"Catering Orders for {week[0]} – {week[-1]}",
        "Please find the catering orders attached.",
        attachment=str(pdf_output)
    )

if __name__ == "__main__":
    main(next_week(today=(date.today() - timedelta(days=33))))  # Use yesterday as "today" to avoid timezone issues on early-morning runs
