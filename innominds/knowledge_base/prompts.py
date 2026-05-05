"""
Prompt templates for IGEL test case generation.

Provides:
  build_system_prompt()          → static IGEL expert system prompt
  assemble_context_window()      → fit KB chunks into token budget
  build_markdown_user_prompt()   → prompt for detailed markdown test doc
  build_python_user_prompt()     → prompt for pytest Python file
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_CONTEXT_TOKENS = 6000
_CHARS_PER_TOKEN = 3.8   # conservative estimate, avoids importing tiktoken here

# Exact import block generated tests must use — injected verbatim into Python prompt
_REQUIRED_IMPORTS = """\
import time, allure
import pytest
from core.api.UMS import UMS
from core.api.ums_wums_api import UMSWUMSApi
from core.api.auth_token import UMSAuthTokenService
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from bussiness.page_login import ums_login
from config.read_config import ums_cred, device_cred, otp_secrets_cred, root_path
from core.ssh.my_logger import logger
from bussiness.onepassword_otp import OTPGenerator"""


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class PromptContext:
    topic: str
    test_id: str
    feature_area: str
    product: str | None
    context_chunks: list        # list[SearchResult] — avoid circular import
    token_budget: int = MAX_CONTEXT_TOKENS


# ── Public API ────────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    return _SYSTEM_PROMPT


def assemble_context_window(
    results: list,
    token_budget: int = MAX_CONTEXT_TOKENS,
) -> tuple[list, int]:
    """
    Fit retrieved parent_content chunks into the token budget.
    Prioritises higher rrf_score results. Truncates last chunk at word boundary if needed.
    Returns (selected_results, estimated_tokens_used).
    """
    reserve = 800   # headroom for prompt template text
    available = token_budget - reserve

    selected = []
    used = 0

    for result in results:   # already sorted by rrf_score descending
        chunk_tokens = _estimate_tokens(result.parent_content)
        if used + chunk_tokens <= available:
            selected.append(result)
            used += chunk_tokens
        elif available - used > 200:
            # Truncate at word boundary to fill remaining space
            remaining_chars = int((available - used) * _CHARS_PER_TOKEN)
            truncated_content = _truncate_at_word(result.parent_content, remaining_chars)
            # Create a shallow copy with truncated content
            import copy
            r = copy.copy(result)
            r.parent_content = truncated_content + "\n[...truncated]"
            selected.append(r)
            used += _estimate_tokens(truncated_content)
            break
        else:
            break

    logger.debug("Context window: %d chunks, ~%d tokens", len(selected), used)
    return selected, used


def build_markdown_user_prompt(ctx: PromptContext) -> str:
    selected, tokens_used = assemble_context_window(ctx.context_chunks, ctx.token_budget)
    context_block = _format_context_block(selected)
    sources = ", ".join(dict.fromkeys(r.file_name for r in selected)) or "IGEL documentation"

    return f"""Generate a JIRA-level detailed IGEL test case document using the knowledge base context below.

TEST REQUEST
============
Test ID      : {ctx.test_id}
Topic        : {ctx.topic}
Feature Area : {ctx.feature_area}
Product      : {ctx.product or "IGEL OS 12"}
KB Sources   : {sources}

KNOWLEDGE BASE CONTEXT
======================
{context_block}

INSTRUCTIONS
============
Using the context above, generate a complete JIRA-style test case. Match the exact level of
detail shown in IGEL JIRA tickets — specific TC Setup navigation paths, exact CLI commands,
precise expected results with exact UI element names.

OUTPUT FORMAT
=============

# {ctx.test_id}: {ctx.topic}

## Key Details
| Field | Value |
|-------|-------|
| JIRA ID | {ctx.test_id} |
| Category | (infer from feature area and context) |
| Priority | High |
| Type | (Integration / Functional / Hardware-dependent — infer from context) |
| Feature Area | {ctx.feature_area} |
| Product | {ctx.product or "IGEL OS 12"} |
| Source Documents | {sources} |

## Description
(2-3 sentences: what feature is tested, what this test validates, why it matters)

## Additional Information
(Key technical notes as bullet points — include:
- default values and what they mean
- important config file paths like /etc/chromium-browser/... or /var/log/...
- policy names and parameter names from context
- any warnings or platform-specific notes from context)

## Requirements
- IGEL OS version: (from context)
- UMS version: (from context)
- (any app version requirements from context)

## Preconditions
(Bullet list — be specific. Example: "IGEL OS 12 device registered in UMS with online status confirmed in UMS console")

## TC Setup — Configuration Navigation Paths
(List all UMS/device configuration steps using the exact path format:
`TC Setup > [Section] > [SubSection] > [Setting] = [value]`
Example: `TC Setup: Apps > Zoom > Zoom Sessions > Session Name = "Test_Session"`)

## Test Details

### Test Step Table
Three columns: **STEP** | **TEST DATA** | **EXPECTED RESULT**

| # | STEP | TEST DATA | EXPECTED RESULT |
|---|------|-----------|-----------------|

For each step:
- STEP: Brief title of what is being verified (e.g., "Check Hardware Video Acceleration")
- TEST DATA: Numbered sub-steps with exact actions. Include:
  * TC Setup navigation paths: `TC Setup: Apps > [App] > [Setting] = true/false`
  * Exact CLI commands with full syntax: `ps ax | grep process-name`
  * Exact file paths: `/var/log/user/app.log`
  * Specific URLs for verification: `chrome://media-internals`
  * Policy/config values: `HardwareAccelerationModeEnabled`
- EXPECTED RESULT: Specific verifiable outcomes. Include:
  * Exact UI elements visible (e.g., "Home, Chat, Meetings, Contacts tabs visible")
  * Exact log output expected (e.g., "journalctl shows no errors for process X")
  * Specific commands and their expected output
  * Pass/fail criterion with exact wording

Minimum 4 test steps. Each step must have at least 2 sub-steps in TEST DATA column.

## Cleanup
| Step | Action | Command/Navigation | Verification |
|------|--------|--------------------|-------------|
(Specific cleanup steps — detach profiles, reboot, verify clean state)

## Troubleshooting
| # | Issue | Symptoms | Root Cause | Fix |
|---|-------|----------|------------|-----|
(Minimum 3 specific issues from context — include exact diagnostic commands)

Generate the complete document now. Use specific IGEL terminology, exact navigation paths,
real CLI commands, and concrete expected values. Never write "TBD" or "[add here]"."""


def build_python_user_prompt(ctx: PromptContext, markdown_content: str) -> str:
    test_id_upper = ctx.test_id.upper()
    slug = _slugify(ctx.topic)
    filename = f"test_{ctx.test_id}_{slug}.py"
    # Extract step count hint from markdown
    step_count = max(markdown_content.lower().count("#### step"), 3)

    return f"""Generate a Python pytest file for the following IGEL test case.

SPECIFICATION (from markdown test case)
========================================
{markdown_content[:4000]}

STRICT REQUIREMENTS — follow exactly, no deviations
=====================================================

1. FILE NAME: {filename}

2. MODULE DOCSTRING (copy this template exactly):
\"\"\"
Test ID    : {ctx.test_id}
Title      : {ctx.topic}
Feature    : {ctx.feature_area}
Product    : {ctx.product or "IGEL OS 12"}
Description: [1-sentence description from specification above]
Author     : IGEL QA Automation (AI-Generated)
\"\"\"

3. IMPORTS — copy these verbatim, do not add or remove any:
{_REQUIRED_IMPORTS}

4. MODULE-LEVEL (after imports):
click = OcrUiInteractor()

5. HELPER FUNCTIONS:
def get_ssh():
    return SSHClient(host=device_cred["host"], user=device_cred["user"],
                     pwd=device_cred["pwd"], port=device_cred["port"])

def _assign(ums, wums, device, profile_key, default_name, api_config):
    profile = ums.get_profile_details(api_config.get(profile_key, default_name))
    wums.assign_object(device["id"], profile["id"], "profile")
    return profile

def _detach(ums, wums, device, profile_key, default_name, api_config):
    profile = ums.get_profile_details(api_config.get(profile_key, default_name))
    wums.detach_profile(device["id"], profile["id"])

6. STEP FUNCTIONS — generate {step_count} steps + 1 cleanup:
   - Decorator: @allure.step("{test_id_upper} SN: [short description]")
   - Signature: def {test_id_upper}_stepN(api_config, browser): -> bool
   - Body pattern:
     try:
         ums  = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
         wums = UMSWUMSApi(ums_cred["weburl"], ums_cred["username"], ums_cred["password"])
         dev  = ums.get_vm_details(device_cred["hostname"])
         [step implementation from specification]
         return True / return result_bool
     except Exception as e:
         logger.error(f"{test_id_upper}_stepN: {{e}}"); return False

   - Cleanup: @allure.step("{test_id_upper} Cleanup: [description]")
     def {test_id_upper}_cleanup(api_config): -> bool

7. TEST FUNCTIONS — one per step, SINGLE LINE each:
   @allure.feature("{ctx.feature_area}")
   @allure.severity(allure.severity_level.CRITICAL)
   def test_{ctx.test_id}_step1(api_config, browser_instance): assert {test_id_upper}_step1(api_config, browser_instance)

   @allure.feature("{ctx.feature_area}")
   @allure.severity(allure.severity_level.CRITICAL)
   def test_{ctx.test_id}_step2(api_config, browser_instance): assert {test_id_upper}_step2(api_config, browser_instance)

   [continue for each step, then:]

   @allure.feature("{ctx.feature_area}")
   @allure.severity(allure.severity_level.MINOR)
   def test_{ctx.test_id}_cleanup(api_config): assert {test_id_upper}_cleanup(api_config)

8. RULES:
   - ALL configurable values from api_config dict — NEVER hardcode IPs, URLs, passwords
   - Use device_cred["hostname"], device_cred["host"], ums_cred["base_url"], ums_cred["weburl"]
   - Use click.is_text_present_on_screen() and click.click_text_on_screen() for OCR checks
   - Use ssh.exec("command") for device shell commands
   - Every step function returns bool
   - No TODO comments, no placeholder text
   - No additional imports beyond the verbatim block above

Generate the complete Python file now. Output raw Python only — no markdown fences."""


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN)


def _truncate_at_word(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    return truncated[:last_space] if last_space > 0 else truncated


def _format_context_block(results: list) -> str:
    if not results:
        return "(No relevant KB content found)"
    parts = []
    for i, r in enumerate(results, start=1):
        parts.append(
            f"=== SOURCE {i}: {r.section_title or r.file_name} ===\n"
            f"Product: {r.product} | File: {r.file_name} | Type: {r.chunk_type} | "
            f"Relevance: {r.rrf_score:.4f}\n\n"
            f"{r.parent_content.strip()}"
        )
    return "\n\n" + "\n\n---\n\n".join(parts) + "\n"


def _slugify(text: str) -> str:
    import re
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s]", "", slug)
    slug = re.sub(r"\s+", "_", slug.strip())
    return slug[:50]


# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior IGEL QA automation engineer with deep expertise in testing IGEL products.
Your job is to generate precise, complete, and executable test cases based ONLY on the
documentation context provided. Never invent steps, settings, or expected values not
explicitly present in the context.

IGEL PRODUCT KNOWLEDGE
======================
- UMS (Universal Management Suite): Central device management server. REST API on HTTPS port 8443.
  URL pattern: https://<ums-ip>:8443/umsapi/v3/. Used to manage profiles, assign them to devices,
  and issue commands (reboot, factory reset). Web UI at https://<ums-ip>:8443/webapp/.
- IGEL OS 12: Linux-based thin client operating system. SSH accessible as root on port 22.
  Device can be controlled via UMS API (profiles) and directly via SSH commands.
- COSMOS: Cloud-based management platform for IGEL devices (cloud alternative to on-prem UMS).
- ICG (IGEL Cloud Gateway): Secure reverse proxy allowing UMS to communicate with devices
  outside the corporate network without VPN.
- IMI (IGEL Management Interface): REST API for programmatic UMS control (token-based auth).
- SSO Providers: Entra ID (Microsoft Azure AD), Okta, PingOne, Omnissa Horizon.

TEST AUTOMATION FRAMEWORK
=========================
- Python + pytest with Allure reporting
- UMS class: core.api.UMS — manages device/profile assignments via REST
- UMSWUMSApi class: core.api.ums_wums_api — assign/detach profiles, device operations
- SSHClient: core.ssh.ssh — execute shell commands on IGEL device via SSH
- OcrUiInteractor (click): core.ui.ui_automation_text — OCR-based screen validation and interaction
- ums_login: bussiness.page_login — Playwright browser automation for UMS Web UI
- OTPGenerator: bussiness.onepassword_otp — TOTP generation for MFA flows
- Configuration: config.read_config — ums_cred, device_cred, otp_secrets_cred, root_path
- api_config: loaded from testdata/sso/api_config.yaml["igel"] — profile names, usernames, etc.

GENERATION RULES
================
1. Use ONLY the provided KB context passages. If a step is not in the context, do not include it.
2. ALL configurable values (profile names, URLs, usernames) come from api_config["key"] or
   ums_cred/device_cred dicts. NEVER hardcode actual IPs, passwords, or credentials.
3. For markdown: follow the template structure exactly with all required sections and tables.
4. For Python: step functions MUST return bool; test functions MUST be single-line assert calls.
5. Be specific: use actual IGEL terminology, SSH commands, and OCR check patterns from context.
6. Cleanup steps are mandatory — always detach profiles and reboot the device.
"""
