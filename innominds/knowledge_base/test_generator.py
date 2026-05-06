"""
IGEL Test Case Generator — LLM Orchestration

Orchestrates:
  1. KB retrieval (retriever.py)
  2. Prompt assembly (prompts.py)
  3. Two Azure GPT-4.1 calls (markdown spec → Python pytest file)
  4. Syntax validation + file writing
"""
from __future__ import annotations

import ast
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from openai import AzureOpenAI, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from knowledge_base.config import cfg
from knowledge_base.retriever import retrieve_v3
from knowledge_base.prompts import (
    PromptContext,
    build_system_prompt,
    build_markdown_user_prompt,
    build_python_user_prompt,
    _slugify,
)

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "Generated"

_REQUIRED_IMPORT_MARKERS = [
    "allure", "UMS", "SSHClient", "OcrUiInteractor",
    "ums_login", "ums_cred", "device_cred", "logger",
]

_FEATURE_KEYWORDS: dict[str, str] = {
    "sso": "SSO Validation",
    "entra": "SSO Validation",
    "okta": "SSO Validation",
    "pingone": "SSO Validation",
    "omnissa": "SSO Validation",
    "ums": "UMS Configuration",
    "profile": "UMS Configuration",
    "wums": "UMS Configuration",
    "reset": "Device Lifecycle",
    "upgrade": "Device Lifecycle",
    "downgrade": "Device Lifecycle",
    "factory": "Device Lifecycle",
    "citrix": "Session Connection",
    "rdp": "Session Connection",
    "avd": "Session Connection",
    "horizon": "Session Connection",
    "windows 365": "Session Connection",
    "certificate": "Security & Certificates",
    "cert": "Security & Certificates",
    "rmagent": "Security & Certificates",
    "obs": "Device Management",
    "broadcast": "Device Management",
    "cic": "Corporate Identity Customization",
    "branding": "Corporate Identity Customization",
    "data retention": "Data Management",
    "ssh": "Device Management",
}


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class GeneratedTestCase:
    test_id: str
    topic: str
    feature_area: str
    product: str | None
    markdown_path: Path | None
    python_path: Path | None
    kb_sources: list[str]
    kb_chunk_count: int
    tokens_used: int
    generation_time_sec: float
    syntax_valid: bool
    warnings: list[str] = field(default_factory=list)
    retrieval_debug: str | None = None


# ── Public API ────────────────────────────────────────────────────────────────

def generate_test_cases(
    topic: str,
    output_format: str = "both",
    product: str | None = None,
    test_id: str | None = None,
    feature_area: str | None = None,
    top_k: int = 8,
    output_dir: Path | None = None,
    debug_retrieval: bool = False,
) -> GeneratedTestCase:
    """
    Generate a test case from the IGEL Knowledge Base.

    Args:
        topic:         Natural language description, e.g. "Entra ID SSO login validation"
        output_format: "md", "py", or "both"
        product:       Optional KB filter — "UMS", "IGEL OS", "COSMOS", "ICG", "IMI"
        test_id:       Custom ID like "TC015". Auto-generated if None.
        feature_area:  Allure feature group. Auto-inferred from topic if None.
        top_k:         Number of KB chunks to retrieve.
        output_dir:    Where to write files. Defaults to tests/Generated/.

    Returns:
        GeneratedTestCase with paths and metadata.

    Raises:
        ValueError: if no KB content found for topic.
        RuntimeError: if LLM calls fail after retries.
    """
    t0 = time.time()
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Retrieve KB context (V3: RRF → rerank → KG → fused budget)
    bundle = retrieve_v3(query=topic, top_k=top_k, product=product)
    if not bundle.results:
        raise ValueError(
            f"No KB content found for topic '{topic}'. "
            "Ensure documents are ingested: python -m knowledge_base.ingest"
        )

    retrieval_debug_json: str | None = bundle.debug.to_json() if debug_retrieval else None
    if debug_retrieval:
        bundle.debug.log_summary()
        logger.debug("Retrieval trace JSON:\n%s", retrieval_debug_json)

    # Step 2: Resolve test_id and feature_area
    resolved_test_id = test_id or _resolve_test_id(output_dir)
    resolved_feature = feature_area or _infer_feature_area(topic)

    tokens_used = bundle.debug.total_tokens_used

    ctx = PromptContext(
        topic=topic,
        test_id=resolved_test_id,
        feature_area=resolved_feature,
        product=product,
        context_chunks=bundle.results,
        token_budget=int(cfg.CONTEXT_TOKEN_BUDGET),
        kg_context_block=bundle.kg_context.text_block,
        image_context_block=bundle.image_block,
        skip_assemble_window=True,
    )

    system_prompt = build_system_prompt()
    warnings: list[str] = []
    md_path: Path | None = None
    py_path: Path | None = None

    # Step 3a: Generate markdown (if requested)
    markdown_content = ""
    if output_format in ("md", "both"):
        logger.info("Generating markdown for '%s'...", topic)
        markdown_user_prompt = build_markdown_user_prompt(ctx)
        markdown_content = _call_gpt(system_prompt, markdown_user_prompt, max_tokens=4096, temperature=0.2)
        md_filename = f"{resolved_test_id}_{_slugify(topic)}.md"
        md_path = _safe_write_path(output_dir / md_filename)
        md_path.write_text(markdown_content, encoding="utf-8")
        logger.info("Markdown written: %s", md_path)

    # Step 3b: Generate Python (if requested)
    syntax_valid = True
    if output_format in ("py", "both"):
        logger.info("Generating Python test file for '%s'...", topic)
        # If we didn't generate markdown yet, do a lightweight context for python prompt
        if not markdown_content:
            md_for_python = _build_minimal_spec(ctx)
        else:
            md_for_python = markdown_content
        python_user_prompt = build_python_user_prompt(ctx, md_for_python)
        python_content = _call_gpt(system_prompt, python_user_prompt, max_tokens=3072, temperature=0.1)
        python_content = _strip_code_fences(python_content)

        # Validate syntax
        syntax_valid, syntax_errors = _validate_python_syntax(python_content)
        import_warnings = _check_required_imports(python_content)
        warnings.extend(syntax_errors)
        warnings.extend(import_warnings)

        py_filename = f"test_{resolved_test_id}_{_slugify(topic)}.py"
        if not syntax_valid:
            py_filename += ".invalid"
            logger.warning("Generated Python has syntax errors — saved as .invalid: %s", syntax_errors)

        py_path = _safe_write_path(output_dir / py_filename)
        py_path.write_text(python_content, encoding="utf-8")
        logger.info("Python test written: %s", py_path)

    elapsed = round(time.time() - t0, 1)
    kb_sources = list(dict.fromkeys(r.file_name for r in bundle.results))

    return GeneratedTestCase(
        test_id=resolved_test_id,
        topic=topic,
        feature_area=resolved_feature,
        product=product,
        markdown_path=md_path,
        python_path=py_path,
        kb_sources=kb_sources,
        kb_chunk_count=len(bundle.results),
        tokens_used=tokens_used,
        generation_time_sec=elapsed,
        syntax_valid=syntax_valid,
        warnings=warnings,
        retrieval_debug=retrieval_debug_json,
    )


def batch_generate(
    topics: list[str],
    output_format: str = "both",
    product: str | None = None,
    feature_area: str | None = None,
    top_k: int = 8,
    output_dir: Path | None = None,
    debug_retrieval: bool = False,
) -> list[GeneratedTestCase]:
    """Generate test cases for multiple topics with auto-incrementing test IDs."""
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve starting test ID once, then increment manually to avoid re-scanning each iteration
    base_id = _resolve_test_id(output_dir)
    base_num = int(re.search(r"\d+", base_id).group())

    results_list: list[GeneratedTestCase] = []
    for i, topic in enumerate(topics):
        current_id = f"TC{(base_num + i):03d}"
        try:
            result = generate_test_cases(
                topic=topic,
                output_format=output_format,
                product=product,
                test_id=current_id,
                feature_area=feature_area,
                top_k=top_k,
                output_dir=output_dir,
                debug_retrieval=debug_retrieval,
            )
            results_list.append(result)
        except Exception as e:
            logger.error("batch_generate: failed for topic '%s': %s", topic, e)
            results_list.append(GeneratedTestCase(
                test_id=current_id,
                topic=topic,
                feature_area=feature_area or _infer_feature_area(topic),
                product=product,
                markdown_path=None,
                python_path=None,
                kb_sources=[],
                kb_chunk_count=0,
                tokens_used=0,
                generation_time_sec=0.0,
                syntax_valid=False,
                warnings=[f"FAILED: {e}"],
                retrieval_debug=None,
            ))

    return results_list


# ── LLM Call ──────────────────────────────────────────────────────────────────

_llm_client: AzureOpenAI | None = None


def _get_llm_client() -> AzureOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AzureOpenAI(
            api_key=cfg.AZURE_API_KEY,
            azure_endpoint=cfg.AZURE_ENDPOINT,
            api_version=cfg.AZURE_API_VERSION,
        )
    return _llm_client


@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_gpt(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    client = _get_llm_client()
    response = client.chat.completions.create(
        model=cfg.AZURE_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = response.choices[0].message.content or ""
    logger.debug("GPT response: %d chars", len(content))
    return content


# ── Post-Processing ───────────────────────────────────────────────────────────

def _strip_code_fences(code: str) -> str:
    code = re.sub(r"^```python\s*\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"^```\s*\n?", "", code, flags=re.MULTILINE)
    return code.strip()


def _validate_python_syntax(code: str) -> tuple[bool, list[str]]:
    try:
        ast.parse(code)
        return True, []
    except SyntaxError as e:
        return False, [f"SyntaxError at line {e.lineno}: {e.msg}"]


def _check_required_imports(code: str) -> list[str]:
    missing = []
    for marker in _REQUIRED_IMPORT_MARKERS:
        if marker not in code:
            missing.append(f"MISSING_IMPORT: '{marker}' not found in generated code")
    return missing


def _safe_write_path(path: Path) -> Path:
    """Return path with _v2, _v3 suffix if file already exists."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for v in range(2, 20):
        candidate = parent / f"{stem}_v{v}{suffix}"
        if not candidate.exists():
            return candidate
    return path  # overwrite as last resort


# ── Test ID Resolution ────────────────────────────────────────────────────────

def _resolve_test_id(output_dir: Path) -> str:
    """Find highest TC number in project and return next one (e.g. TC011)."""
    search_dirs = [
        output_dir,
        Path(__file__).resolve().parents[1] / "tests" / "Testscript_10",
    ]
    pattern = re.compile(r"test_TC(\d+)", re.IGNORECASE)
    highest = 0

    for d in search_dirs:
        if not d.exists():
            continue
        for f in d.rglob("test_TC*.py"):
            m = pattern.search(f.name)
            if m:
                highest = max(highest, int(m.group(1)))

    return f"TC{highest + 1:03d}"


# ── Feature Area Inference ────────────────────────────────────────────────────

def _infer_feature_area(topic: str) -> str:
    topic_lower = topic.lower()
    for keyword, area in _FEATURE_KEYWORDS.items():
        if keyword in topic_lower:
            return area
    return "IGEL Validation"


def _build_minimal_spec(ctx: PromptContext) -> str:
    """Minimal spec for Python generation when markdown was not generated."""
    return (
        f"Test ID: {ctx.test_id}\n"
        f"Topic: {ctx.topic}\n"
        f"Feature Area: {ctx.feature_area}\n"
        f"Product: {ctx.product or 'IGEL OS 12'}\n\n"
        "Generate test steps based on standard IGEL testing patterns for this topic."
    )
