"""Generate per-session catering orders for the upcoming week as a markdown file."""
from pathlib import Path

from src.business import llm
from src.persistence import helpers
from src.shared.dates import next_week

def filter_menu(menu: list[tuple[str, list[str]]], dietary_tags: list[str]) -> list[tuple[str, list[str]]]:
    """Filter the menu to the dishes that meet the student's dietary requirements."""
    filtered = []
    requirements = set(dietary_tags)
    for name, tags in menu:
        if requirements.issubset(set(tags)):
            filtered.append((name, tags))
    return filtered

def pick_dish(student_dietary: list[str], menu: list[tuple[str, list[str]]]) -> str:
    requirements = set(student_dietary)
    for name, tags in menu:
        if requirements.issubset(tags):
            return name
    return menu[0][0] if menu else "<no menu>"


def build_session_table(program_id: int, session_date: str, menu: list[tuple[str, list[str]]]) -> list[str]:
    students = helpers.get_students_for_session(program_id, session_date)
    if not students:
        return ["_No catering required._"]

    # Students with free-text dietary requirements go through the LLM individually;
    # the rest fall into the standard dish-count table via the greedy picker.
    standard = [(sid, diet) for sid, diet, extra in students if not extra]
    special = [(sid, diet, extra) for sid, diet, extra in students if extra]

    lines: list[str] = []

    if standard:
        counts: dict[str, int] = {}
        for _, dietary in standard:
            dish = pick_dish(dietary, menu)
            counts[dish] = counts.get(dish, 0) + 1
        lines.append("| Dish | Quantity |")
        lines.append("|------|----------|")
        for dish, qty in sorted(counts.items()):
            lines.append(f"| {dish} | {qty} |")

    if special:
        if standard:
            lines.append("")
        lines.append("**Special dietary requirements:**")
        lines.append("")
        lines.append("| Dietary Requirements | Recommended Dish |")
        lines.append("|----------------------|------------------|")
        for _, tags, extra in special:
            requirements = ", ".join([*tags, extra]) if tags else extra
            dish = llm.find_meal(extra, filter_menu(menu, tags))
            lines.append(f"| {requirements} | {dish} |")

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
        "th { background-color: #f0f0f0; }"
    )
    pdf = MarkdownPdf()
    pdf.add_section(Section(md_path.read_text(encoding="utf-8")), user_css=css)
    pdf.save(str(pdf_path))


def main() -> None:
    week = next_week()
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
        menu = helpers.get_menu(caterer_id)
        programs = helpers.get_programs(school_id)

        session_printed = False
        for program_id, day, start, end, mgr_name, mgr_mobile in programs:
            session_rows = helpers.get_sessions(program_id, week)
            for session_date, sub_name, sub_mobile in sorted(session_rows):
                session_printed = True
                sections.append(f"### {session_date} ({day} {start}–{end})")
                sections.append("")
                sections.append(format_manager_line(mgr_name, mgr_mobile, sub_name, sub_mobile))
                sections.append("")
                sections.extend(build_session_table(program_id, session_date, menu))
                sections.append("")

        if not session_printed:
            sections.append("_No sessions scheduled this week._")
            sections.append("")

    output = Path() / "output" / "orders.md"
    output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Wrote {output}")

    pdf_output = output.with_suffix(".pdf")
    markdown_to_pdf(output, pdf_output)
    print(f"Wrote {pdf_output}")


if __name__ == "__main__":
    main()
