"""Generate per-session catering orders as a markdown file."""
from pathlib import Path

from src.persistence import helpers


def pick_dish(student_dietary: list[str], menu: list[tuple[str, list[str]]]) -> str:
    requirements = set(student_dietary)
    for name, tags in menu:
        if requirements.issubset(tags):
            return name
    return menu[0][0] if menu else "<no menu>"


def build_session_table(session_id: int, menu: list[tuple[str, list[str]]]) -> list[str]:
    students = helpers.get_students(session_id)
    if not students:
        return ["_No students enrolled._"]

    counts: dict[str, int] = {}
    for _, dietary in students:
        dish = pick_dish(dietary, menu)
        counts[dish] = counts.get(dish, 0) + 1

    lines = ["| Dish | Quantity |", "|------|----------|"]
    for dish, qty in sorted(counts.items()):
        lines.append(f"| {dish} | {qty} |")
    return lines


def markdown_to_pdf(md_path: Path, pdf_path: Path) -> None:
    from markdown_pdf import MarkdownPdf, Section

    pdf = MarkdownPdf()
    pdf.add_section(Section(md_path.read_text(encoding="utf-8")))
    pdf.save(str(pdf_path))


def main() -> None:
    sections: list[str] = ["# Catering Orders", ""]

    for school_id, school_name in helpers.get_schools():
        sections.append(f"## {school_name}")
        sections.append("")

        caterer_id = helpers.get_caterer(school_id)
        menu = helpers.get_menu(caterer_id)
        sessions = helpers.get_sessions(school_id)

        if not sessions:
            sections.append("_No sessions._")
            sections.append("")
            continue

        for session_id, day, start, end in sessions:
            sections.append(f"### {day} {start}–{end}")
            sections.append("")
            sections.extend(build_session_table(session_id, menu))
            sections.append("")

    output = Path() / "output" / "orders.md"
    output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Wrote {output}")

    pdf_output = output.with_suffix(".pdf")
    markdown_to_pdf(output, pdf_output)
    print(f"Wrote {pdf_output}")


if __name__ == "__main__":
    main()
