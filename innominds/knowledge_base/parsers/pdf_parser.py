"""
PDF Parser — three-tier strategy:
  Tier 1: If a pre-converted markdown file exists in markdown_output/, use it.
           (Higher quality — processed by marker-pdf + Azure OpenAI LLM)
  Tier 2: Direct pdfplumber extraction.
  Tier 3: PyMuPDF (fitz) fallback — handles PDFs pdfplumber can't (encrypted
           XRefs, exotic fonts, malformed cross-reference tables).
"""
import logging
from pathlib import Path
from knowledge_base.parsers.markdown_parser import Section, parse_markdown_file, find_markdown_for_pdf

logger = logging.getLogger(__name__)


def parse_pdf(pdf_path: Path, markdown_output_dir: Path) -> tuple[list[Section], str]:
    """
    Returns (sections, parse_method) where parse_method is one of:
    'markdown', 'pdfplumber', 'pymupdf'.
    """
    # Tier 1: use pre-converted markdown
    md_path = find_markdown_for_pdf(pdf_path.name, markdown_output_dir)
    if md_path:
        sections = parse_markdown_file(md_path)
        if sections:
            return sections, "markdown"

    # Tier 2: pdfplumber
    try:
        sections = _parse_with_pdfplumber(pdf_path)
        if sections and any(s.content.strip() for s in sections):
            return sections, "pdfplumber"
        logger.info("pdfplumber returned empty sections for %s — trying PyMuPDF", pdf_path.name)
    except Exception as e:
        logger.warning("pdfplumber failed on %s: %s — falling back to PyMuPDF", pdf_path.name, e)

    # Tier 3: PyMuPDF
    sections = _parse_with_pymupdf(pdf_path)
    return sections, "pymupdf"


def _parse_with_pymupdf(pdf_path: Path) -> list[Section]:
    import fitz
    sections: list[Section] = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.error("PyMuPDF could not open %s: %s", pdf_path.name, e)
        return [Section(title=pdf_path.stem, level=0, content="", page_hint=1)]

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text") or ""
            text = text.strip()
            if not text:
                continue
            sections.append(Section(
                title=pdf_path.stem,
                level=0,
                content=text,
                page_hint=page_idx + 1,
            ))
    finally:
        doc.close()

    return sections if sections else [Section(title=pdf_path.stem, level=0, content="", page_hint=1)]


def _parse_with_pdfplumber(pdf_path: Path) -> list[Section]:
    import pdfplumber
    import re

    all_sections: list[Section] = []
    current_title = pdf_path.stem
    current_level = 0
    current_lines: list[str] = []
    current_page = 1
    full_text_lines: list[str] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Extract tables first — preserve as markdown
            tables = page.extract_tables()
            table_md_blocks = [_table_to_markdown(t) for t in tables if t]

            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            lines = text.split("\n")

            # Strip header/footer (first and last line are usually page number / product name)
            if len(lines) > 3:
                lines = lines[1:-1]

            for line in lines:
                line = line.strip()
                if not line:
                    full_text_lines.append("")
                    continue

                # Heading detection by ALL_CAPS short lines or common IGEL heading patterns
                if _is_heading(line):
                    # Flush current section
                    content = "\n".join(current_lines).strip()
                    if content:
                        all_sections.append(Section(
                            title=current_title,
                            level=current_level,
                            content=content,
                            page_hint=current_page,
                        ))
                    current_title = line.rstrip(":")
                    current_level = _estimate_heading_level(line)
                    current_lines = []
                    current_page = page_num
                else:
                    current_lines.append(line)
                    full_text_lines.append(line)

            # Append tables as a block at end of page content
            for table_md in table_md_blocks:
                current_lines.append(table_md)

    # Flush final section
    content = "\n".join(current_lines).strip()
    if content:
        all_sections.append(Section(
            title=current_title,
            level=current_level,
            content=content,
            page_hint=current_page,
        ))

    # If no structure detected, treat whole doc as one section
    if len(all_sections) <= 1:
        all_text = "\n".join(full_text_lines).strip()
        return [Section(title=pdf_path.stem, level=0, content=all_text, page_hint=1)]

    return all_sections


def _is_heading(line: str) -> bool:
    import re
    if len(line) > 120:
        return False
    # Short ALL CAPS lines
    if line.isupper() and 3 < len(line) < 80:
        return True
    # Numbered heading: "1.2 Title" or "3. Title"
    if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]", line):
        return True
    # Lines ending with colon that look like section titles
    if line.endswith(":") and len(line) < 60 and line[0].isupper():
        return True
    return False


def _estimate_heading_level(line: str) -> int:
    import re
    m = re.match(r"^(\d+)(\.\d+)*", line)
    if m:
        depth = line[:line.index(" ")].count(".")
        return min(depth + 1, 3)
    return 2


def _table_to_markdown(table: list) -> str:
    if not table or not table[0]:
        return ""
    rows = [[str(cell or "").strip() for cell in row] for row in table]
    # Find max columns
    cols = max(len(r) for r in rows)
    rows = [r + [""] * (cols - len(r)) for r in rows]

    header = "| " + " | ".join(rows[0]) + " |"
    divider = "| " + " | ".join(["---"] * cols) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join([header, divider] + body)
