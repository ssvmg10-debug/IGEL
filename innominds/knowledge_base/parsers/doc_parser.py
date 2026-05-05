"""
DOC / DOCX Parser
Strategy:
  .docx → python-docx (best fidelity, preserves headings/tables)
  .doc  → mammoth → fallback → win32com (Windows COM via installed MS Word)
"""
import re
from pathlib import Path
from knowledge_base.parsers.markdown_parser import Section


def parse_doc(file_path: Path) -> list[Section]:
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return _parse_docx(file_path)
    elif suffix == ".doc":
        return _parse_doc_binary(file_path)
    raise ValueError(f"Unsupported doc type: {suffix}")


# ── DOCX ─────────────────────────────────────────────────────────────────────

def _parse_docx(path: Path) -> list[Section]:
    from docx import Document
    doc = Document(str(path))

    sections: list[Section] = []
    current_title = path.stem
    current_level = 0
    current_paragraphs: list[str] = []

    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        text = para.text.strip()

        if not text:
            continue

        # Detect headings by style
        heading_match = re.match(r"Heading (\d+)", style_name)
        if heading_match:
            # Flush current section
            content = "\n\n".join(current_paragraphs).strip()
            if content:
                sections.append(Section(
                    title=current_title,
                    level=current_level,
                    content=content,
                ))
            current_title = text
            current_level = int(heading_match.group(1))
            current_paragraphs = []
        else:
            current_paragraphs.append(text)

    # Flush last section
    content = "\n\n".join(current_paragraphs).strip()
    if content:
        sections.append(Section(title=current_title, level=current_level, content=content))

    # Extract tables and append as extra sections
    for i, table in enumerate(doc.tables):
        md_table = _docx_table_to_markdown(table)
        if md_table:
            sections.append(Section(
                title=f"Table {i+1}",
                level=3,
                content=md_table,
                metadata={"is_table": True},
            ))

    return sections if sections else [Section(title=path.stem, level=0, content=_docx_full_text(doc))]


def _docx_full_text(doc) -> str:
    return "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())


def _docx_table_to_markdown(table) -> str:
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(cells)
    if not rows:
        return ""
    cols = max(len(r) for r in rows)
    rows = [r + [""] * (cols - len(r)) for r in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    divider = "| " + " | ".join(["---"] * cols) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join([header, divider] + body)


# ── DOC (binary) ──────────────────────────────────────────────────────────────

def _parse_doc_binary(path: Path) -> list[Section]:
    text = ""

    # Attempt 1: mammoth (handles some .doc files)
    try:
        import mammoth
        with open(str(path), "rb") as f:
            result = mammoth.extract_raw_text(f)
        text = result.value.strip()
        if len(text) > 200:
            return _text_to_sections(text, path.stem)
    except Exception:
        pass

    # Attempt 2: Windows COM (requires MS Word installed)
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc_obj = word.Documents.Open(str(path.resolve()))
        text = doc_obj.Content.Text.strip()
        doc_obj.Close(False)
        word.Quit()
        if text:
            return _text_to_sections(text, path.stem)
    except Exception:
        pass

    # Attempt 3: read raw bytes and extract printable text (last resort)
    try:
        raw = path.read_bytes()
        # DOC files store text in the Word Binary Format — extract ASCII runs
        text = _extract_text_from_binary(raw)
        if len(text) > 100:
            return _text_to_sections(text, path.stem)
    except Exception:
        pass

    raise RuntimeError(f"Could not parse .doc file: {path.name}. "
                       "Try converting to .docx using Microsoft Word or LibreOffice first.")


def _extract_text_from_binary(raw: bytes) -> str:
    """Extract readable text runs from DOC binary format (crude but works for plain content)."""
    import re
    # Extract ASCII sequences of 4+ printable chars
    chunks = re.findall(rb"[\x20-\x7E]{4,}", raw)
    text = " ".join(c.decode("ascii", errors="ignore") for c in chunks)
    # Remove excessive whitespace
    text = re.sub(r"\s{3,}", "\n\n", text)
    return text.strip()


def _text_to_sections(text: str, source_name: str) -> list[Section]:
    """Convert flat text into sections by detecting paragraph boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    sections: list[Section] = []
    current_title = source_name
    current_paras: list[str] = []

    for para in paragraphs:
        # Heuristic: short line that looks like a heading
        if len(para) < 80 and not para.endswith(".") and para[0].isupper():
            if current_paras:
                sections.append(Section(
                    title=current_title,
                    level=2,
                    content="\n\n".join(current_paras),
                ))
            current_title = para
            current_paras = []
        else:
            current_paras.append(para)

    if current_paras:
        sections.append(Section(title=current_title, level=2, content="\n\n".join(current_paras)))

    return sections if sections else [Section(title=source_name, level=0, content=text)]
