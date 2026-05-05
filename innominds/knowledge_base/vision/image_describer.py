"""
Image describer — GPT-4.1 Vision via Azure OpenAI.

Returns a structured ImageDescription per image. The prompt is engineered to
capture EVERY context cue: verbatim text (OCR-grade), UI elements with state,
semantic narrative tied to the source document, and test-relevance hints
(since this KB drives test case generation).
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field

from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from knowledge_base.config import cfg

logger = logging.getLogger(__name__)


@dataclass
class ImageDescription:
    image_type: str = "unknown"
    verbatim_text: str = ""
    ui_elements: list[dict] = field(default_factory=list)
    semantic_description: str = ""
    test_relevance: str = ""
    raw_json: dict = field(default_factory=dict)
    error: str | None = None


_SYSTEM_PROMPT = """You are an expert at analyzing technical documentation images for IGEL OS \
(a Linux-based thin-client OS) and the IGEL Universal Management Suite (UMS).

Your job is to extract every drop of context from each image so it can be \
indexed for retrieval and used to generate functional test cases.

ALWAYS reply with a SINGLE JSON object — no markdown, no commentary outside JSON. \
Schema:

{
  "image_type": "ui_screenshot | configuration_dialog | network_diagram | architecture_diagram | flowchart | table_as_image | screenshot_with_annotations | photo | icon_or_logo | code_snippet | error_message | chart | unknown",
  "verbatim_text": "EVERY visible piece of text in the image, one item per line. Include button labels, menu items, field names, tooltip text, error/status messages, URLs, file paths, version numbers, IP addresses, registry keys, hostnames, code, command names. Preserve exact spelling and casing. If no text is visible, write \\"NONE\\".",
  "ui_elements": [
    {"type": "button|dropdown|checkbox|radio|tab|text_field|toggle|menu_item|link|tree_node|table_cell|panel", "label": "...", "state": "enabled|disabled|checked|unchecked|selected|focused|empty|filled|expanded|collapsed", "value": "current value or selection or null"}
  ],
  "semantic_description": "2-4 specific sentences. Name the IGEL feature, configuration page, dialog, profile, or workflow shown. Reference the surrounding text context. Avoid generic phrases like \\"this image shows a screenshot\\".",
  "test_relevance": "If this image illustrates configuration steps, error states, or feature behavior: list 2-5 concrete test actions a QA engineer could derive (one per line, e.g. \\"Verify SSO login button is enabled when domain field is filled\\"). If purely decorative or a logo: write \\"Reference image only\\"."
}

If any field genuinely has no content, use empty string "" or empty list []. Never omit a key. \
Do not wrap the JSON in code fences."""


_USER_TEMPLATE = """Source document: {document_name}
Section: {section_title}
Page: {page_number}
Caption (if present): {caption}

Surrounding text context from the source document (the paragraphs near this image):
---
{surrounding_text}
---

Analyze the image and return the JSON described in the system prompt."""


class _ImageDescriberClient:
    _client: AzureOpenAI | None = None

    @classmethod
    def get(cls) -> AzureOpenAI:
        if cls._client is None:
            cls._client = AzureOpenAI(
                api_key=cfg.AZURE_API_KEY,
                azure_endpoint=cfg.AZURE_ENDPOINT,
                api_version=cfg.AZURE_API_VERSION,
            )
        return cls._client


@retry(
    reraise=True,
    stop=stop_after_attempt(cfg.MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(Exception),
)
def _call_vision(messages: list, max_tokens: int) -> str:
    client = _ImageDescriberClient.get()
    resp = client.chat.completions.create(
        model=cfg.AZURE_DEPLOYMENT,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "{}"


def describe_image(
    image_bytes: bytes,
    image_format: str,
    document_name: str,
    section_title: str = "",
    page_number: int | None = None,
    caption: str | None = None,
    surrounding_text: str = "",
) -> ImageDescription:
    """Send an image to GPT-4.1 Vision and parse the structured JSON response."""

    # Cap surrounding_text to keep prompt size reasonable
    if len(surrounding_text) > 4000:
        surrounding_text = surrounding_text[:4000] + " […truncated…]"

    mime = "image/jpeg" if image_format.lower() in ("jpg", "jpeg") else f"image/{image_format.lower()}"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    user_text = _USER_TEMPLATE.format(
        document_name=document_name,
        section_title=section_title or "(unknown section)",
        page_number=str(page_number) if page_number else "(n/a)",
        caption=caption or "(none)",
        surrounding_text=surrounding_text or "(none)",
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
        ]},
    ]

    try:
        raw = _call_vision(messages, max_tokens=1500)
    except Exception as e:
        logger.error("Vision call failed for %s: %s", document_name, e)
        return ImageDescription(error=str(e))

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Non-JSON vision response for %s: %s", document_name, raw[:200])
        return ImageDescription(error=f"json: {e}", semantic_description=raw[:500])

    return ImageDescription(
        image_type=str(data.get("image_type", "unknown")),
        verbatim_text=str(data.get("verbatim_text", "")),
        ui_elements=data.get("ui_elements") if isinstance(data.get("ui_elements"), list) else [],
        semantic_description=str(data.get("semantic_description", "")),
        test_relevance=str(data.get("test_relevance", "")),
        raw_json=data,
    )


def build_embedding_text(
    desc: ImageDescription,
    document_name: str,
    section_title: str,
    page_number: int | None,
    caption: str | None,
    surrounding_text: str,
) -> str:
    """Combine all the captured context into a single string that gets embedded.
    This is what similarity search will hit, so include OCR text, the semantic
    description, the section, and key surrounding context."""
    parts = [
        f"[Image from: {document_name}]",
        f"Section: {section_title}" if section_title else "",
        f"Page: {page_number}" if page_number else "",
        f"Caption: {caption}" if caption else "",
        f"Type: {desc.image_type}",
        "",
        "Visible text in image:",
        desc.verbatim_text or "(none)",
        "",
        "Description:",
        desc.semantic_description or "(none)",
        "",
        "Test relevance:",
        desc.test_relevance or "(none)",
    ]
    if surrounding_text:
        parts += ["", "Surrounding document context:", surrounding_text[:1500]]

    if desc.ui_elements:
        ui_lines = []
        for ui in desc.ui_elements[:20]:
            if isinstance(ui, dict):
                ui_lines.append(
                    f"- {ui.get('type','?')}: {ui.get('label','')} "
                    f"[{ui.get('state','')}] "
                    f"= {ui.get('value','')}"
                )
        if ui_lines:
            parts += ["", "UI elements:"] + ui_lines

    return "\n".join(p for p in parts if p != "")
