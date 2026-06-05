from pathlib import Path

def markdown_to_pdf(md_path: Path, pdf_path: Path) -> None:
    from markdown_pdf import MarkdownPdf, Section

    css = (
        "table { border-collapse: collapse; margin: 8px 0; }"
        "th, td { border: 1px solid #888; padding: 4px 8px; }"
    )
    pdf = MarkdownPdf()
    pdf.add_section(Section(md_path.read_text(encoding="utf-8")), user_css=css)
    pdf.save(str(pdf_path))


def slug(name: str) -> str:
    """Filesystem-safe lowercase slug for per-caterer output filenames.
    Non-alphanumeric runs collapse to a single hyphen."""
    _slug = "".join(c if c.isalnum() else "-" for c in name.lower())
    while "--" in _slug:
        _slug = _slug.replace("--", "-")
    return _slug.strip("-")