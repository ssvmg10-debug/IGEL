"""
Image extraction from PDFs, DOCX, and DOC files.

Each extracted image carries enough context to be linked back to its source
document and the nearest text section:
  - bytes (raw, byte-perfect)
  - format / dimensions
  - page_number (PDF) or paragraph_index (DOCX)
  - bbox on page (PDF only)
  - surrounding_text (paragraphs above + below)
  - caption (if heuristically detectable)
"""
from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    sequence_index: int
    image_bytes: bytes
    image_format: str            # "png" | "jpeg" | "jpg" | ...
    width: int | None
    height: int | None
    page_number: int | None      # 1-based for PDFs (first occurrence)
    bbox: dict | None            # {x0,y0,x1,y1} for PDFs (first occurrence)
    surrounding_text: str        # paragraph(s) above + below the FIRST occurrence
    caption: str | None
    occurrence_pages: list[int] = field(default_factory=list)  # all pages this image appears on
    is_recurring: bool = False   # likely header/logo/footer if appears on >25% of pages
    image_hash: str = field(init=False)

    def __post_init__(self):
        self.image_hash = hashlib.sha256(self.image_bytes).hexdigest()


# ── PDFs (PyMuPDF) ────────────────────────────────────────────────────────────

# Filter: skip tiny decorative images and giant page-wide background images
MIN_IMAGE_BYTES = 2 * 1024     # 2 KB
MIN_DIMENSION = 50             # pixels
MAX_DIMENSION = 8000           # pixels (filter out scanned-page backgrounds)


def extract_images_from_pdf(pdf_path: Path) -> list[ExtractedImage]:
    """Extract unique images from a PDF.

    Critical: same logo / header / footer often appears on every page.
    We dedupe by sha256 across the WHOLE document, keep the first occurrence's
    page_number/bbox/surrounding_text, and record all pages it appears on so the
    describer can flag recurring headers.
    """
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.error("PyMuPDF could not open %s: %s", pdf_path.name, e)
        return []

    page_count = len(doc)

    # First pass: build (hash → list of occurrences) and (xref → bytes/meta)
    # An "occurrence" = the page it appeared on, plus first-seen bbox + page text.
    # We process pages in order so the FIRST occurrence becomes the canonical one.
    occurrences: dict[str, dict] = {}   # hash -> {bytes, ext, w, h, first_page, first_bbox, first_page_text, pages: [int]}

    try:
        for page_idx in range(page_count):
            page = doc[page_idx]
            page_num = page_idx + 1
            page_text = page.get_text("text") or ""

            seen_in_page: set[str] = set()
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    info = doc.extract_image(xref)
                except Exception as e:
                    logger.warning("extract_image failed (xref=%s) in %s: %s", xref, pdf_path.name, e)
                    continue

                img_bytes = info.get("image")
                ext = (info.get("ext") or "png").lower()
                w = info.get("width")
                h = info.get("height")

                if not img_bytes or len(img_bytes) < MIN_IMAGE_BYTES:
                    continue
                if w and h:
                    if w < MIN_DIMENSION or h < MIN_DIMENSION:
                        continue
                    if w > MAX_DIMENSION or h > MAX_DIMENSION:
                        continue

                hsh = hashlib.sha256(img_bytes).hexdigest()
                if hsh in seen_in_page:
                    continue
                seen_in_page.add(hsh)

                if hsh in occurrences:
                    # Already recorded — just track the page
                    occurrences[hsh]["pages"].append(page_num)
                    continue

                # First time seeing this image — record canonical position
                bbox = None
                try:
                    rects = page.get_image_rects(xref)
                    if rects:
                        r = rects[0]
                        bbox = {"x0": float(r.x0), "y0": float(r.y0),
                                "x1": float(r.x1), "y1": float(r.y1)}
                except Exception:
                    pass

                occurrences[hsh] = {
                    "bytes": img_bytes,
                    "ext": ext,
                    "w": w, "h": h,
                    "first_page": page_num,
                    "first_page_idx": page_idx,
                    "first_bbox": bbox,
                    "first_page_text": page_text,
                    "pages": [page_num],
                }
    finally:
        # Defer doc.close until after we read previous/next page text below
        pass

    # Second pass: build ExtractedImage per unique hash, with surrounding_text
    # composed from the FIRST page's neighbors. Mark recurring if appears on
    # > 25% of pages.
    images: list[ExtractedImage] = []
    seq = 0
    recurring_threshold = max(3, int(page_count * 0.25))

    try:
        # Sort by first occurrence so sequence_index reflects reading order
        for hsh, occ in sorted(occurrences.items(), key=lambda kv: (kv[1]["first_page"], kv[1]["pages"][0])):
            page_idx = occ["first_page_idx"]
            page_num = occ["first_page"]
            page_text = occ["first_page_text"]

            surrounding_parts = []
            if page_idx > 0:
                try:
                    prev = doc[page_idx - 1].get_text("text") or ""
                    if prev:
                        surrounding_parts.append(prev[-600:].strip())
                except Exception:
                    pass
            if page_text.strip():
                surrounding_parts.append(page_text.strip()[:1500])
            if page_idx + 1 < page_count:
                try:
                    nxt = doc[page_idx + 1].get_text("text") or ""
                    if nxt:
                        surrounding_parts.append(nxt[:600].strip())
                except Exception:
                    pass
            surrounding_text = "\n\n".join(surrounding_parts)

            caption = _find_caption(page_text, occ["first_bbox"])
            occurrence_pages = sorted(set(occ["pages"]))
            is_recurring = len(occurrence_pages) >= recurring_threshold and page_count >= 4

            seq += 1
            images.append(ExtractedImage(
                sequence_index=seq,
                image_bytes=occ["bytes"],
                image_format=occ["ext"],
                width=occ["w"],
                height=occ["h"],
                page_number=page_num,
                bbox=occ["first_bbox"],
                surrounding_text=surrounding_text,
                caption=caption,
                occurrence_pages=occurrence_pages,
                is_recurring=is_recurring,
            ))
    finally:
        doc.close()

    return images


def _find_caption(page_text: str, bbox: dict | None) -> str | None:
    import re
    if not page_text:
        return None
    # Heuristic: find a "Figure N: ..." or "Fig. N ..." or "Table N: ..." line
    m = re.search(r"^(?:Figure|Fig\.|Table)\s*\d+[:.]?\s*[^\n]{0,200}",
                  page_text, flags=re.MULTILINE)
    if m:
        return m.group(0).strip()
    return None


# ── DOCX (python-docx + relationships) ───────────────────────────────────────

# Inline shapes / images live in the document's relationships.
# We iterate paragraphs in order; whenever a run contains a drawing element
# referencing an image relationship, we record that image at that point.

def extract_images_from_docx(docx_path: Path) -> list[ExtractedImage]:
    from docx import Document
    from docx.oxml.ns import qn

    images: list[ExtractedImage] = []
    seq = 0

    try:
        doc = Document(str(docx_path))
    except Exception as e:
        logger.error("python-docx could not open %s: %s", docx_path.name, e)
        return []

    # Build a flat ordered list of (paragraph_index, paragraph_text, image_rels[])
    paragraphs = doc.paragraphs

    # First pass: linearize into events
    events: list[tuple[str, int, str | list]] = []
    # event types: ("text", para_idx, text), ("image", para_idx, [rel_id, ...])
    for p_idx, para in enumerate(paragraphs):
        text = para.text.strip()
        if text:
            events.append(("text", p_idx, text))

        # Find image relationship ids inside this paragraph
        rel_ids: list[str] = []
        for run in para.runs:
            for blip in run._element.iter(qn("a:blip")):
                rid = blip.get(qn("r:embed"))
                if rid:
                    rel_ids.append(rid)
        if rel_ids:
            events.append(("image", p_idx, rel_ids))

    # Second pass: emit ExtractedImage at each "image" event with surrounding text
    rels = doc.part.related_parts
    for ev_idx, ev in enumerate(events):
        if ev[0] != "image":
            continue
        _, p_idx, rel_ids = ev

        # Surrounding text: 2 prior text events + 2 following text events
        before = [e[2] for e in events[max(0, ev_idx - 6):ev_idx] if e[0] == "text"][-3:]
        after = [e[2] for e in events[ev_idx + 1: ev_idx + 7] if e[0] == "text"][:3]
        surrounding_text = "\n\n".join(before + after)

        # Caption: heuristic — paragraph immediately after that starts with Figure/Table
        caption = None
        for e in events[ev_idx + 1: ev_idx + 4]:
            if e[0] == "text":
                t = e[2]
                if t[:7].lower() in ("figure ", "fig. ", "table ") or \
                   t.lower().startswith(("figure", "fig.", "table")):
                    caption = t[:200]
                break

        for rel_id in rel_ids:
            part = rels.get(rel_id)
            if part is None or not hasattr(part, "blob"):
                continue
            img_bytes: bytes = part.blob
            if not img_bytes or len(img_bytes) < MIN_IMAGE_BYTES:
                continue

            # Try to determine format + dimensions via Pillow
            ext = "png"
            w = h = None
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(img_bytes))
                ext = (im.format or "png").lower()
                if ext == "jpeg":
                    ext = "jpg"
                w, h = im.size
                if w < MIN_DIMENSION or h < MIN_DIMENSION:
                    continue
                if w > MAX_DIMENSION or h > MAX_DIMENSION:
                    continue
            except Exception:
                pass

            seq += 1
            images.append(ExtractedImage(
                sequence_index=seq,
                image_bytes=img_bytes,
                image_format=ext,
                width=w,
                height=h,
                page_number=None,            # DOCX has no page numbers without rendering
                bbox=None,
                surrounding_text=surrounding_text,
                caption=caption,
            ))

    return images


# ── DOC binary (Word legacy) — convert to DOCX first via Word COM if available ──

def extract_images_from_doc(doc_path: Path) -> list[ExtractedImage]:
    """Best-effort: convert .doc to .docx via Word COM, then reuse DOCX extractor.
    Returns [] if Microsoft Word isn't available on this host."""
    import tempfile

    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError:
        logger.info("pywin32 not available — cannot extract images from .doc: %s", doc_path.name)
        return []

    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
    except Exception as e:
        logger.info("Microsoft Word COM unavailable — skipping images for %s (%s)", doc_path.name, e)
        return []

    tmp = Path(tempfile.gettempdir()) / f"{doc_path.stem}_converted.docx"
    try:
        d = word.Documents.Open(str(doc_path.resolve()))
        # WdSaveFormat.wdFormatXMLDocument = 12 (.docx)
        d.SaveAs(str(tmp), FileFormat=12)
        d.Close(False)
        word.Quit()
    except Exception as e:
        logger.warning("Could not convert %s -> docx: %s", doc_path.name, e)
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        return []

    if not tmp.exists():
        return []

    images = extract_images_from_docx(tmp)
    try:
        tmp.unlink()
    except Exception:
        pass
    return images


# ── Dispatcher ────────────────────────────────────────────────────────────────

def extract_images(file_path: Path) -> list[ExtractedImage]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_images_from_pdf(file_path)
    if suffix == ".docx":
        return extract_images_from_docx(file_path)
    if suffix == ".doc":
        return extract_images_from_doc(file_path)
    # CSV, MD, MHT, etc. — no embedded images
    return []
