"""
Parses pre-converted Markdown files from marker-pdf output.
Priority: if a PDF already has a markdown_output folder, use it — it's higher quality
than raw pdfplumber extraction because it's been processed with Azure OpenAI LLM.
"""
import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Section:
    title: str
    level: int          # 1=H1, 2=H2, 3=H3, 0=no heading
    content: str
    page_hint: int = 0  # approximate page (from image filenames or context)
    metadata: dict = field(default_factory=dict)


def parse_markdown_file(md_path: Path) -> list[Section]:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    return _split_into_sections(text, str(md_path.name))


def _split_into_sections(text: str, source_name: str) -> list[Section]:
    # Strip HTML comments (marker-pdf source headers)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()

    lines = text.split("\n")
    sections: list[Section] = []
    current_title = source_name
    current_level = 0
    current_lines: list[str] = []
    page_hint = 1

    for line in lines:
        heading_match = re.match(r"^(#{1,4})\s+(.+)", line)
        if heading_match:
            # Flush previous section
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(Section(
                    title=current_title,
                    level=current_level,
                    content=content,
                    page_hint=page_hint,
                ))
            current_title = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_lines = []
        else:
            # Track page hints from image references like images/page_5_img_1.png
            page_ref = re.search(r"page_(\d+)", line)
            if page_ref:
                page_hint = int(page_ref.group(1))
            current_lines.append(line)

    # Flush last section
    content = "\n".join(current_lines).strip()
    if content:
        sections.append(Section(
            title=current_title,
            level=current_level,
            content=content,
            page_hint=page_hint,
        ))

    # Merge tiny orphan sections (heading-only, < 50 chars) into next sibling
    return _merge_orphan_sections(sections)


def _merge_orphan_sections(sections: list[Section]) -> list[Section]:
    merged: list[Section] = []
    i = 0
    while i < len(sections):
        sec = sections[i]
        # If this section has almost no content and there's a next section at same/lower level
        if len(sec.content) < 60 and i + 1 < len(sections):
            next_sec = sections[i + 1]
            # Prepend this section's content into next section with heading as context
            next_sec.content = f"**{sec.title}**\n{sec.content}\n\n{next_sec.content}".strip()
            i += 1
            continue
        merged.append(sec)
        i += 1
    return merged


def find_markdown_for_pdf(pdf_filename: str, markdown_output_dir: Path) -> Path | None:
    """
    Given a PDF filename, find its pre-converted markdown file in markdown_output/.
    Returns the .md file path if found, else None.
    """
    stem = Path(pdf_filename).stem
    # Normalize: spaces → underscores, remove parens/commas (matches convert_pdfs.py logic)
    safe_dir = stem.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    md_path = markdown_output_dir / safe_dir / f"{stem}.md"

    if md_path.exists():
        return md_path

    # Also try with cleaned filename
    for folder in markdown_output_dir.iterdir():
        if folder.is_dir():
            candidate = folder / f"{folder.name}.md"
            if candidate.exists() and _fuzzy_match(stem, folder.name):
                return candidate

    return None


def _fuzzy_match(a: str, b: str) -> bool:
    """Simple match ignoring spaces, underscores, case."""
    norm = lambda s: s.lower().replace("_", "").replace(" ", "").replace("-", "")
    return norm(a) in norm(b) or norm(b) in norm(a)
