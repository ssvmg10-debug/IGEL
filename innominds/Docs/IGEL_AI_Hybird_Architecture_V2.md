**IGEL AI-Powered Test Generation**

Hybrid Architecture — Production Design Document

Version 2.0 · May 2026 · IGEL QA & Engineering

_Prepared by: Innominds QA Automation Team in collaboration with IGEL Engineering_

Audience: QA Leadership · Engineering Architecture · Product Management

| 81 Docs Ingested | 53,123 Chunks in pgvector | 7 Validation Gates | 14K+ TCs Target Scale |
| --- | --- | --- | --- |

# Table of Contents

# 1\. Executive Summary

This document defines the production-grade Hybrid Architecture for IGEL's AI-powered test case generation and automation script generation system. It supersedes the previous BM25-only approach and the standalone Claude Code 5-layer approach by combining the best of both into a single, validated, scalable pipeline.

| CORE GOAL | Generate detailed, executable IGEL test cases and pytest automation scripts from IGEL's knowledge base with >90% accuracy, validated at every stage, scalable to 14,000+ test cases, and integrated into the existing Bitbucket / TeamCity CI/CD pipeline. |
| --- | --- |

## 1.1 Why a Hybrid Architecture

Neither approach alone is sufficient for IGEL's use case:

*   The Innominds RAG + pgvector approach provides the critical knowledge retrieval foundation — parent-child chunking, image intelligence, hybrid BM25 + vector search, and live Jira/Confluence context. Without this, any LLM generating IGEL test cases will hallucinate registry keys, navigation paths, and UMS API details.
*   The Claude Code 5-layer approach provides the agentic execution foundation — CLAUDE.md as the agent's constitution, Skills for framework-aware code generation, Hooks as deterministic quality guardrails, and Subagents for parallel workload delegation. Without this, automation scripts lack awareness of your actual pytest fixtures, SSH helpers, and UMS API wrappers.
*   Neither approach has a systematic validation layer. The most critical missing component — verified at every phase before output is accepted — is a multi-gate validation pipeline that catches hallucinated steps, schema violations, invalid registry keys, and broken script imports before a human ever sees the output.

## 1.2 Two Outputs, One Pipeline

| Output Artifact | Format | Destination | Accuracy Target |
| --- | --- | --- | --- |
| Test case document | QCAPPS-* Jira Markdown | Jira via API after human approval | >90% step accuracy |
| Automation script | Executable pytest (.py) | Bitbucket repo via PR after review | >85% runnable without edits |

## 1.3 The Seven Validation Gates

Every phase in this pipeline has a defined validation gate. A TC or script that fails any gate is either auto-repaired or routed to the failed queue — it never reaches the human reviewer as broken output. The seven gates are:

| Gate | Phase | What It Checks | Auto-Repair? |
| --- | --- | --- | --- |
| G1 — Ingestion integrity | Phase 1 | Every document parsed without data loss; chunk count within bounds | Yes — re-parse |
| G2 — Retrieval relevance | Phase 2 | Top-K chunks share ≥2 keywords with TC topic; RRF score above threshold | Yes — widen search |
| G3 — Schema compliance | Phase 3 | Generated TC JSON matches required schema; all fields populated | Yes — retry once |
| G4 — Domain accuracy | Phase 4 | Registry keys, TC Setup paths, and UMS API calls verified against known corpus | No — human queue |
| G5 — Step completeness | Phase 4 | Preconditions, numbered steps, expected results, and cleanup all present | Yes — patch missing |
| G6 — Script executability | Phase 5 | Generated pytest imports resolve; fixtures exist in conftest; syntax valid | Yes — regenerate |
| G7 — Human approval | Phase 6 | QA engineer approves TC and script before Jira/repo push | N/A — required |

# 2\. Architecture Overview

The Hybrid Architecture operates as a seven-phase sequential pipeline. Each phase is independently deployable, testable, and observable. The diagram below shows the data flow:

| HYBRID PIPELINE — HIGH LEVEL DATA FLOW[IGEL Docs / Jira / Confluence]|PHASE 1 — Ingestion & Chunking [G1]|PHASE 2 — Hybrid Retrieval [G2]|PHASE 3 — TC Generation (Claude) [G3]|PHASE 4 — Validation Layer [G4][G5]|PHASE 5 — Script Generation [G6]|PHASE 6 — Human Review Gate [G7]|PHASE 7 — Publish (Jira / Bitbucket) |
| --- |

## 2.1 Technology Stack

| Layer | Technology | Purpose | Replaces |
| --- | --- | --- | --- |
| Vector store | PostgreSQL 17 + pgvector | Embedding storage, hybrid search, RRF fusion | Flat BM25 in-memory index |
| Embedding model | text-embedding-3-large (3072-dim) | Semantic chunk indexing + image description indexing | — |
| Image intelligence | Claude claude-sonnet-4-20250514 Vision | OCR + UI element extraction from IGEL screenshots | Ignored images |
| Test generation LLM | Claude claude-sonnet-4-20250514 (Anthropic) | TC document + script generation with context-only rule | Generic prompts |
| Agent framework | Claude Code (CLAUDE.md + Skills + Hooks) | Framework-aware script generation with guardrails | Stateless API calls |
| Orchestration | Python 3.12 async workers + Redis queue | Batch processing, rate limiting, checkpointing | Sequential loop |
| CI/CD | TeamCity + Bitbucket pipelines | Automated generation runs + PR-based script review | Manual runs |
| Monitoring | Structured JSON logs + Prometheus metrics | Per-phase observability, quality dashboards | Print statements |
| Review UI | Self-contained HTML dashboard | QA engineer TC approval workflow | Email-based review |
| PHASE 1 · Knowledge Base IngestionParse → Chunk (Parent+Child) → Embed → Store → Validate [G1] |
| --- |

Phase 1 builds and maintains the knowledge base that grounds every test case generation. It is the most critical phase — the quality of retrieval in Phase 2 is a direct function of ingestion quality here. Every architectural decision in this phase serves one goal: maximise the precision and recall of subsequent retrieval.

## 3.1 Document Sources

| Category | Sources | Count | Format | Update Frequency |
| --- | --- | --- | --- | --- |
| A — Public docs | IGEL OS, UMS 12.x admin guide, ICG, IMI API, Apps guide, HW compatibility | 81 docs | PDF, Word | Per IGEL release |
| B — Internal QA | Historical TC templates, defect reports, test plans, quick-start guides | Curated set | CSV, MD, Word | As produced |
| C — Live: Jira | QCAPPS-* test case tickets, APPS-* feature/bug tickets | Continuous | Jira API | Real-time (pending) |
| D — Live: Confluence | Apps Testing space — TC Setup paths, registry keys, changelogs | Continuous | Confluence API | Real-time (pending) |

## 3.2 Hierarchical Chunking — Parent + Child Architecture

This is the single most impactful design decision in the pipeline. Flat chunking at a fixed token size degrades both retrieval precision and LLM context quality. The two-level hierarchy solves both problems simultaneously.

| PARENT CHUNK (800–1,200 tokens) — passed to LLM as contextFull section: all registry keys, TC Setup paths, version notes, behavioral descriptions|+-- CHILD CHUNK 1 (150–300 tokens) — indexed in pgvector| "SSO login via Entra ID: app.zoom.global.sso_enabled = true"+-- CHILD CHUNK 2 (150–300 tokens) — indexed in pgvector| "Clear Login Data: app.zoom.global.keep_login_data = false"+-- CHILD CHUNK 3 (150–300 tokens) — indexed in pgvector"Known issue: Zoom 6.2.x keeps users signed in on ARM when keep_login_data=false" |
| --- |

### How retrieval uses the hierarchy

1.  Child chunks are searched — small size = precise match to query intent
2.  Matched children identify their parent section via foreign key
3.  Full parent section is fetched and passed to Claude as context
4.  LLM receives complete picture: all keys, paths, edge cases, version notes

## 3.3 Image Intelligence Pipeline

IGEL documentation is heavily visual. Configuration dialogs, UMS Web UI screenshots, registry navigation trees, and architecture diagrams contain test-critical information that text extraction alone misses entirely. This pipeline extracts that information.

| Stage | Tool | Output | Filter Criteria |
| --- | --- | --- | --- |
| Extract from PDF/DOCX | PyMuPDF + python-docx | Raw image bytes + page number + bounding box + surrounding text (4,000 chars) | — |
| Recurring image detection | SHA-256 hash frequency analysis | Skip headers, logos, watermarks appearing on >25% of pages | Frequency > 25% |
| Global deduplication | SHA-256(image_bytes) lookup in kb_images | Skip identical images across all documents | Hash collision |
| Vision analysis | Claude claude-sonnet-4-20250514 Vision API | Structured JSON: image_type, verbatim_text, ui_elements[], semantic_description, test_relevance | — |
| Relevance filter | Rule-based on Vision output | Skip decorative images with empty verbatim_text and no ui_elements | Zero test value |
| Embed + store | text-embedding-3-large on combined description text | 3,072-dim vector in kb_images.description_embedding | — |

## 3.4 Validation Gate G1 — Ingestion Integrity

| Validation Check | How It Is Verified | Failure Action |
| --- | --- | --- |
| Document parsed without error | Parser returns non-empty content for every ingested file | Re-parse with fallback parser; alert if second parse also fails |
| Chunk count within expected bounds | parent_count ≥ (page_count / 4); child_count ≥ (parent_count × 3) | Flag document for manual review; do not index partial chunks |
| No duplicate documents re-ingested | file_hash UNIQUE constraint in kb_documents; skip on collision | Log and skip; trigger only if hash changes (document updated) |
| Image extraction completeness | image_count per document matches PyMuPDF image manifest count (minus filtered) | Log missing images; continue ingestion but flag document |
| Embedding dimension consistency | All embedding vectors are exactly 3,072 dimensions | Reject chunk; log embedding API error; retry once before alerting |
| PHASE 2 · Hybrid Retrieval EngineVector Search + BM25 + RRF Fusion + Image Context [G2] |
| --- |

Phase 2 is executed for every test case generation request. Given a TC topic or summary, it retrieves the most relevant knowledge from pgvector and returns enriched context to the LLM. The hybrid approach is mandatory — neither vector search nor BM25 alone is sufficient for IGEL's mixed query types.

## 4.1 Why Hybrid Search Is Required

| Query Type | Example | Vector Search | BM25 / Full-Text | Required Approach |
| --- | --- | --- | --- | --- |
| Exact term match | app.zoom.global.keep_login_data | Misses — too specific for semantic similarity | Finds exactly — term matching | BM25 required |
| Semantic concept | Entra ID SSO login validation | Finds — even if doc says 'Azure AD' or 'OIDC' | Misses — terminology mismatch | Vector required |
| Mixed | Zoom 6.3 SSO on AMD clear login data | Partial — catches semantic but misses exact key | Partial — catches key but misses version context | Both required (RRF) |

## 4.2 Retrieval Pipeline — Step by Step

1.  Embed query using text-embedding-3-large (3,072-dim vector)
2.  Vector search: SELECT parent\_chunk\_id, cosine\_similarity FROM kb\_chunks ORDER BY embedding <=> query\_vec LIMIT 32
3.  Full-text search: SELECT parent\_chunk\_id, ts\_rank FROM kb\_chunks WHERE tsvector\_content @@ plainto\_tsquery(query) LIMIT 32
4.  Reciprocal Rank Fusion: RRF\_score(chunk) = Σ 1/(60 + rank). Merges both lists, rewarding chunks that rank well in both.
5.  Deduplicate by parent\_chunk\_id — if multiple children share a parent, keep only the highest-scoring child → prevents redundant context
6.  Fetch full parent content for top-K parent IDs — returns 800–1,200 token sections
7.  Inline image context — for each returned parent, fetch related images from kb\_images WHERE parent\_chunk\_id = ? AND image\_type NOT IN ('recurring\_header\_or\_logo')
8.  Assemble context window: 8 parent sections + image descriptions = ~5,000–6,000 tokens

## 4.3 Validation Gate G2 — Retrieval Relevance

| Validation Check | How It Is Verified | Failure Action |
| --- | --- | --- |
| Minimum RRF score threshold | Top result RRF score must be > 0.02; below this indicates the query found nothing meaningful | Expand search to top-64; if still below threshold, flag TC for manual KB gap analysis |
| Topic keyword overlap | At least 2 keywords from TC summary appear in retrieved chunks' tsvector content | Widen search; add synonym expansion for IGEL-specific terms (UMS→management suite, ICG→cloud gateway) |
| Product filter alignment | Retrieved chunks match the TC's IGEL product tag (OS12, UMS, ICG, COSMOS) | Add product filter to query; re-run retrieval with explicit product constraint |
| Context token budget not exceeded | Total assembled context stays within 7,000 tokens (leaves room for system prompt + output) | Trim lowest-scoring parent sections; truncate image descriptions before parent text |
| PHASE 3 · Test Case Generation — LLM OrchestrationSystem Prompt + Context → QCAPPS-Format TC Document [G3] |
| --- |

Phase 3 passes the assembled context from Phase 2 to Claude along with a carefully crafted system prompt that establishes the IGEL QA expert persona and strict generation rules. The output is a validated JSON document matching the QCAPPS-\* Jira format.

## 5.1 The IGEL Expert System Prompt

The system prompt is not a generic instruction — it encodes IGEL-specific domain knowledge that would otherwise require expensive context. It establishes:

*   Persona: senior IGEL QA automation engineer with explicit product knowledge (UMS REST API on port 8443, IGEL OS 12 SSH on port 22, ICG reverse proxy architecture, SSO providers)
*   Context-only rule: 'Generate test steps ONLY from the provided KB context. Never invent steps, settings, or expected values not explicitly present in the retrieved documentation.'
*   Naming rules: TC Setup navigation paths must be exact (e.g., TC Setup > Apps > Zoom > Settings); registry keys must use actual IGEL naming (e.g., app.zoom.global.keep\_login\_data)
*   Cleanup mandate: cleanup steps are required — always detach profiles and reboot the device after every test
*   Output schema: strict JSON only — no prose, no markdown fences, must match the defined schema

## 5.2 Two-Pass Generation

| Pass | Input | Output | Max Tokens | Model |
| --- | --- | --- | --- | --- |
| Pass 1 — TC document | System prompt + KB context + TC metadata | QCAPPS-* format JSON: objective, environment, preconditions, numbered steps with expected results, cleanup, automation metadata | 4,096 | claude-sonnet-4-20250514 |
| Pass 2 — Pytest script | Pass 1 TC document + framework repo context (CLAUDE.md + relevant fixtures) | Executable pytest script using actual IGEL framework helpers | 3,000 | claude-sonnet-4-20250514 |

## 5.3 QCAPPS-Compatible Output Schema

The JSON schema produced by Pass 1 must match this structure exactly. All fields are required — missing fields trigger auto-repair (see Gate G3):

{

"objective": "One sentence — what this TC validates",

"environment": {

"hardware": "IGEL Certified hardware, e.g. UD3-LX51",

"igel\_os\_version": "IGEL OS 12.x latest",

"ums\_version": "UMS 12.x latest",

"network": "Device reachable from UMS over TCP 30001",

"additional": "VDI server, certificates, test accounts"

},

"preconditions": \[ "Item 1", "Item 2", "..." \],

"test\_steps": \[

{ "step\_number": 1, "action": "Navigate to...", "expected\_result": "..." }

\],

"expected\_final\_result": "Overall PASS criteria",

"cleanup\_steps": \[ "Revert profile", "Reboot device" \],

"automation\_candidate": true,

"automation\_complexity": "low | medium | high",

"automation\_notes": "Which framework layer handles this",

"estimated\_minutes": 15,

"kb\_sources": \[ "chunk\_id\_1", "chunk\_id\_2" \],

"tags": \[ "UMS", "Zoom", "SSO", "OS12" \]

}

## 5.4 Validation Gate G3 — Schema Compliance

| Validation Check | How It Is Verified | Failure Action |
| --- | --- | --- |
| All required fields present | JSON schema validator against defined schema; checks all keys exist | Retry generation once with explicit field reminder in prompt; log if second attempt fails |
| Minimum step count | test_steps array must have ≥ 3 steps | Retry with instruction: 'The test case requires at least 5 detailed steps' |
| Every step has expected_result | Schema validator checks each step object for action AND expected_result | Patch step by re-running Pass 1 with step-level instruction |
| Preconditions array not empty | preconditions.length ≥ 2 | Auto-patch: add standard IGEL preconditions (device online in UMS, credentials available) |
| Cleanup steps present | cleanup_steps.length ≥ 1 | Auto-patch: insert standard cleanup (detach profile, send reboot command via UMS API) |
| JSON parse succeeds | json.loads() with repair for minor formatting issues (stray fences, leading prose) | Retry once; if second attempt still invalid JSON, route to failed queue for manual review |
| PHASE 4 · Domain Accuracy ValidationRegistry Keys · Navigation Paths · UMS API · Step Quality [G4][G5] |
| --- |

Phase 4 is the most important gate in the entire pipeline and the component absent from both previous approaches. It validates the factual domain accuracy of every generated test case against verified IGEL knowledge — not just structural compliance, but actual correctness of IGEL-specific content.

| WHY THIS PHASE EXISTS | An LLM can generate structurally valid test cases that contain completely wrong IGEL content: a registry key that does not exist, a TC Setup path with the wrong menu depth, a UMS API endpoint that was renamed in version 12.4. These errors look correct to a reviewer unfamiliar with the specific feature area. Domain validation catches them automatically. |
| --- | --- |

## 6.1 Registry Key Validator

A registry key corpus is built from all registry key mentions in the KB (extracted during ingestion using the regex pattern app\\.\[a-z0-9\_\]+\\.\[a-z0-9\_.\]+). Every registry key in a generated TC is checked against this corpus:

| Check | Implementation | Pass Condition | Fail Action |
| --- | --- | --- | --- |
| Key exists in corpus | Exact match lookup in registry_key_corpus table | Key found with exact spelling | Flag for human review; suggest nearest match (edit distance ≤ 2) |
| Key value type is valid | Value type check against corpus (boolean, string, integer, enum) | Generated value matches declared type | Auto-correct boolean strings to true/false; flag enum mismatches |
| Key applies to correct product | Cross-reference key's product_scope in corpus | Key is valid for the TC's product (OS12, UMS, ICG) | Flag — key may be from wrong product version |

## 6.2 TC Setup Navigation Path Validator

TC Setup paths follow a strict hierarchical pattern. All valid paths are extracted during ingestion and stored in a path\_registry table. Every path in a generated TC is validated:

| Check | Method | Example Valid Path | Example Invalid Path |
| --- | --- | --- | --- |
| Path depth ≥ 3 levels | Split on '>' and count segments | TC Setup > Apps > Zoom > Settings | TC Setup > Zoom (too shallow — ambiguous) |
| Path exists in path_registry | Exact match with normalised whitespace | TC Setup > User Interface > Screensaver > Timeout | TC Setup > UI > Screensaver > Timeout (wrong level name) |
| Path applies to correct OS version | Cross-reference path's version_introduced | Valid in OS 12.x | Path removed in OS 12.3 — regenerate with updated path |

## 6.3 UMS API Validator

For test cases involving UMS REST API calls (assign profile, reboot device, check device status), every API call in the generated TC is validated against the IMI API guide that was ingested in Phase 1:

*   Endpoint exists: GET/POST/PUT path matches a known endpoint in the IMI guide
*   Port is correct: UMS API is always HTTPS port 8443 — flag any other port reference
*   Required parameters: body parameters match the documented schema for that endpoint
*   Response format: expected result references the correct HTTP status code (200, 204, etc.)

## 6.4 Validation Gate G4 — Domain Accuracy

| Validation Check | How It Is Verified | Failure Action |
| --- | --- | --- |
| All registry keys validated | Every key in test_steps and preconditions checked against registry_key_corpus | Route to human review queue; highlight failed keys with suggested corrections |
| All TC Setup paths validated | Every path in test_steps checked against path_registry | Route to human review queue; show nearest valid path from registry |
| UMS API calls validated | Every API endpoint in generated steps checked against IMI guide corpus | Route to human review queue; cite the correct endpoint from KB |
| KB source confidence score | Each generated step should trace to at least one retrieved chunk (cosine sim > 0.7) | Flag steps with no KB backing as 'potentially hallucinated' in review UI |

## 6.5 Validation Gate G5 — Step Completeness

| Validation Check | How It Is Verified | Failure Action |
| --- | --- | --- |
| Preconditions cover hardware and credentials | NLP check: does preconditions mention device/hardware AND credentials/account? | Auto-patch: append standard IGEL preconditions from template library |
| Steps cover the full test lifecycle | Steps must include: setup/assign, trigger/action, verify/assert, cleanup | Re-run Pass 1 with explicit instruction: 'Include setup, action, verification, and cleanup steps' |
| Expected results are specific | Each expected_result must be > 20 characters and not just 'Success' or 'Pass' | Re-run with instruction: 'Expected results must state what is observed on screen or in logs' |
| Estimated execution time is realistic | estimated_minutes must be between 5 and 120; values outside this range are suspicious | Set to null; surface to reviewer for manual entry |
| PHASE 5 · Automation Script Generation — Claude Code AgentCLAUDE.md + Skills + Hooks → Executable Pytest [G6] |
| --- |

Phase 5 converts validated TC documents into executable pytest scripts using the Claude Code 5-layer agentic framework. Unlike Phase 3 which uses a stateless API call, Phase 5 runs an agent that reads your actual framework code to generate scripts that work with your existing fixtures, helpers, and patterns.

## 7.1 The Five Layers Applied to IGEL

| Layer | IGEL-Specific Content | Purpose in Script Generation |
| --- | --- | --- |
| Layer 1: CLAUDE.md (Memory / Constitution) | Framework structure map: where conftest.py fixtures live, SSH helper location, UMS API wrapper paths, OCR utility imports, pytest mark definitions (@pytest.mark.igel_os, @pytest.mark.ums) | Agent always knows the framework rules before writing a single line |
| Layer 2: Skills (Knowledge Layer) | SKILL_ums_api.md: UMS REST API patterns with real examples SKILL_ssh.md: Paramiko SSH patterns for IGEL OS SKILL_playwright.md: Browser automation for UMS Web UI SKILL_ocr.md: Screenshot validation patterns | Task-specific context loaded on demand — only relevant skill is loaded per TC type |
| Layer 3: Hooks (Guardrail Layer) | PreToolUse: block any write to production UMS URL PostToolUse: auto-lint generated script (flake8 + mypy) Stop: post Slack notification with script path and TC key | Deterministic quality gates that cannot be bypassed by the agent |
| Layer 4: Subagents (Delegation Layer) | Parallel script generation: one subagent per TC batch code-reviewer subagent: validates imports and fixture usage test-runner subagent: runs script in dry-run mode against mock UMS | Keeps main agent context clean; enables parallel batch generation |
| Layer 5: Plugins (Distribution Layer) | IGEL framework plugin: packages Skills + CLAUDE.md for team install New team members install plugin to get full framework context immediately | Distributes the agent's framework knowledge across the team |

## 7.2 Framework-Aware Script Generation

The key difference between Phase 5 and a naive API call is that the agent reads your actual conftest.py and helper files before generating. This produces scripts that use real fixture names, not invented ones:

\# Generated by Phase 5 agent — uses real framework fixtures

import pytest

from framework.ums\_api import UMSClient

from framework.ssh\_helper import IGELDevice

from framework.ocr import assert\_screen\_contains

@pytest.mark.ums

@pytest.mark.igel\_os

class TestZoomSSOLoginMethods:

def test\_entra\_id\_sso\_login(self, ums\_client: UMSClient,

igel\_device: IGELDevice, api\_config):

"""TC011: Entra ID SSO Login Validation — generated from QCAPPS-1249"""

profile\_name = api\_config\['sso\_profile\_name'\]

\# Step 1: Assign SSO profile via UMS API

ums\_client.assign\_profile(igel\_device.id, profile\_name)

ums\_client.wait\_for\_online(igel\_device.id, timeout=90)

\# Step 2: Trigger reboot and verify online

ums\_client.reboot\_device(igel\_device.id)

igel\_device.wait\_for\_ssh(timeout=120)

\# Step 3: Validate Entra ID login screen via VNC

assert\_screen\_contains(igel\_device, 'Microsoft', timeout=30)

\# Cleanup — always executed

ums\_client.detach\_profile(igel\_device.id, profile\_name)

ums\_client.reboot\_device(igel\_device.id)

## 7.3 Validation Gate G6 — Script Executability

| Validation Check | How It Is Verified | Failure Action |
| --- | --- | --- |
| Python syntax is valid | ast.parse() on generated script; zero syntax errors required | Re-generate script; if second attempt fails, route to human queue |
| All imports resolve | Run python -c 'import <module>' for every import statement in framework context | Replace unresolvable import with correct framework import; log substitution |
| All fixtures exist in conftest | Parse conftest.py fixture names; verify every pytest fixture argument is defined | Replace with nearest fixture name; flag in review if no match found |
| Cleanup steps are present | Script must contain a teardown section or try/finally block | Append standard IGEL cleanup block from framework template |
| No hardcoded credentials | Regex scan for password=, api_key=, token= with literal string values | Replace with api_config['key'] pattern; alert on every occurrence |
| No hardcoded UMS production URL | Hook: block write if script contains production UMS hostname | Block generation; require parameterised UMS URL from api_config |
| Dry-run execution passes | Run pytest --collect-only on generated script in CI sandbox; collection must succeed | Flag as collection error; route to human review with error output |
| PHASE 6 · Human Review GateQA Approval Dashboard → Approve / Reject / Edit → Route [G7] |
| --- |

Phase 6 is the mandatory human checkpoint before any AI-generated content reaches Jira or the Bitbucket repository. The HTML review dashboard surfaces all validation results alongside the generated content, making it fast and informed — not a blind rubber-stamp.

## 8.1 Review Dashboard Features

*   Sidebar list of all generated TCs in the batch with status (pending / approved / rejected) and validation summary badge
*   Detail view showing: objective, environment, preconditions, numbered steps, expected results, cleanup — all formatted identically to the Jira QCAPPS-\* view
*   Inline validation panel: registry keys highlighted green (validated) or red (failed); TC Setup paths with validation status; confidence score per step
*   KB source traceability: every generated step shows which KB chunk(s) backed it — reviewer can click to read the source documentation
*   One-click Approve / Reject / Edit per TC and per script
*   Batch export: exports approved\_tcs.json for Jira push and approved\_scripts/ folder for Bitbucket PR
*   Progress tracker: approved count / total, with estimated Jira push time

## 8.2 Review Time Estimates

| Scenario | Validation Pass Rate | Est. Time per TC | 1,800 TC Batch Time |
| --- | --- | --- | --- |
| All gates pass, strong KB coverage | >85% gates pass | 2–3 min | ~6–9 hours (distributed over days) |
| Mixed — some domain validation flags | 60–85% gates pass | 4–6 min (flags need reading) | ~12–18 hours |
| Weak KB coverage for topic area | <60% gates pass | 8–12 min (verify manually) | Route batch for KB enrichment first |
| REVIEW EFFICIENCY TIP | Sort the dashboard by 'confidence score descending' to review high-confidence TCs first. Approve these quickly, then spend detailed review time on flagged TCs. Target: reviewers should not be correcting structural errors — those are caught by Gates G3–G5. Reviewers should only be making domain judgement calls that require human expertise. |
| --- | --- |
| PHASE 7 · Publish — Jira Update + Bitbucket PRApproved TCs → Jira API · Approved Scripts → Bitbucket PR |
| --- |

## 9.1 Jira Update Flow

1.  Read approved\_tcs.json (exported from review dashboard)
2.  For each approved TC: load enriched\_tc\_XXXX.json from local output directory
3.  Call Jira REST API v3: PUT /rest/api/3/issue/{issue\_key} with ADF-formatted description
4.  Update includes: objective, environment table, preconditions list, numbered steps table, expected final result, cleanup steps, automation candidate badge
5.  Add label 'ai-enriched' and 'ai-version:2.0' to TC for traceability
6.  Write push receipt to pushed\_tcs\_YYYYMMDD.json — permanent audit log

| SAFETY DEFAULT | The Jira pusher always defaults to dry_run=True. Live push requires explicit flag --no-dry-run AND interactive confirmation. This cannot be bypassed by the CI/CD pipeline — only human-triggered runs can push to Jira. |
| --- | --- |

## 9.2 Bitbucket Pull Request Flow

1.  Create a new branch: igel-ai-scripts/{batch-id}/{date}
2.  Copy all approved script files to tests/generated/{product}/{feature}/ directory
3.  Run pytest --collect-only on all new scripts in the CI environment — must pass
4.  Run flake8 + mypy on all new scripts — zero errors required
5.  Open Bitbucket PR with: generated TC count, pass/fail summary, link to review dashboard batch, link to validation report
6.  Assign PR reviewer to the QA engineer who approved the batch in Phase 6
7.  PR merge triggers TeamCity pipeline: runs new tests against IGEL test lab

# 10\. CI/CD Integration — TeamCity + Bitbucket

## 10.1 Pipeline Topology

The IGEL AI generation pipeline is integrated into the existing TeamCity + Bitbucket infrastructure with three distinct pipeline types:

| Pipeline | Trigger | Stages | Duration |
| --- | --- | --- | --- |
| KB Ingestion Pipeline | New IGEL release docs committed to Bitbucket | Parse → Chunk → Embed → Store → G1 Validate → Alert if fails | 20–60 min depending on doc volume |
| TC Enrichment Pipeline | Scheduled: weekly or manual trigger | Load thin TCs → Retrieve → Generate → G3 Validate → Local output | 1.5h for 1,800 TCs at 45 RPM |
| Script Generation Pipeline | After TC batch is reviewed and approved_tcs.json is committed | Load approved TCs → Generate scripts → G6 Validate → Open Bitbucket PR | ~30 min for 100 TCs |

## 10.2 TeamCity Build Configuration — TC Enrichment

\# Build step 1: Setup

pip install -r requirements.txt --break-system-packages

\# Build step 2: Analyze (free — no API calls)

python cli.py analyze --csv %JIRA\_CSV\_PATH% --threshold 300

\# Build step 3: Enrich (uses ANTHROPIC\_API\_KEY from TC secure store)

python cli.py enrich \\

\--csv %JIRA\_CSV\_PATH% \\

\--kb %KB\_MD\_PATH% \\

\--model claude-sonnet-4-20250514 \\

\--rpm 45 \\

\--batch-size 20 \\

\--resume %CHECKPOINT\_PATH% # safe restart on failure

\# Build step 4: Publish review dashboard URL

echo "Review dashboard: %OUTPUT\_DIR%/batch\_review.html"

## 10.3 Secure Credential Management

| Credential | Storage | Scope | Rotation Policy |
| --- | --- | --- | --- |
| ANTHROPIC_API_KEY | TeamCity secure parameter | TC Enrichment + Script Gen pipelines only | Rotate every 90 days |
| JIRA_API_TOKEN | TeamCity secure parameter | Jira pusher only — never in enrichment pipeline | Rotate every 90 days |
| POSTGRES_PASSWORD | TeamCity secure parameter + .env for local dev | KB ingestion + retrieval | Rotate every 180 days |
| CONFLUENCE_API_TOKEN | TeamCity secure parameter | Confluence MCP when IGEL access granted | Rotate every 90 days |

## 10.4 Failure Recovery

All three pipelines are designed for safe restart. The TC Enrichment pipeline writes a checkpoint.json after every batch of 20 TCs. If the pipeline fails at TC 450 of 1,800, re-running with --resume checkpoint.json skips the 450 already processed and continues from TC 451. No duplicate generations.

# 11\. Scalability — 1,800 TCs Today to 14,000+ Tomorrow

## 11.1 Current State vs. Target Scale

| Dimension | Current (1,800 TCs) | Near-term (5,000 TCs) | Target (14,000+ TCs) |
| --- | --- | --- | --- |
| Jira projects | QCL + QCAPPS (2) | All IGEL products (6–8) | All products + apps (20+) |
| KB documents | 81 docs ingested | 200+ docs | 500+ docs + live Confluence |
| KB chunks (pgvector) | 53,123 units | 150,000+ units | 500,000+ units |
| Generation time | ~1.5h at 45 RPM | ~4h with 2 workers | ~10h with 8 parallel workers |
| Infrastructure | Single PostgreSQL instance | Read replica + connection pooling | PgBouncer + horizontal read replicas |
| Estimated API cost | $8–15 per run | $25–45 per run | $80–120 per run |

## 11.2 Scaling the Generation Workers

The batch runner is designed for horizontal scaling. To scale from 1 worker to N workers, replace the sequential loop in BatchRunner with a Redis-backed task queue:

\# Current: sequential

for tc in thin\_tcs:

result = enricher.enrich(tc)

\# Scaled: N parallel workers via Redis queue

from celery import Celery

app = Celery('igel\_enrich', broker='redis://localhost:6379/0')

@app.task(bind=True, max\_retries=3)

def enrich\_tc\_task(self, tc\_dict):

tc = TestCase(\*\*tc\_dict)

return enricher.enrich(tc).to\_dict()

\# Dispatch — 8 workers at 6 RPM each = 48 RPM total (under 50 RPM limit)

for tc in thin\_tcs:

enrich\_tc\_task.delay(tc.to\_dict())

## 11.3 PostgreSQL Scaling Path

| Scale Level | Configuration | Trigger Condition |
| --- | --- | --- |
| Level 1 (current) | Single PostgreSQL 17 instance, ivfflat index (lists=100) | Up to 200K chunks; query latency <100ms |
| Level 2 | Add read replica; route retrieval queries to replica | When write load from ingestion impacts read latency |
| Level 3 | PgBouncer connection pooler; increase ivfflat lists to 200 | When concurrent retrieval workers exceed 10 |
| Level 4 | Migrate to HNSW index (hnsw m=16, ef_construction=64) | When ivfflat recall degrades below 95% at 500K+ chunks |

# 12\. Roadmap & Open Items

## 12.1 Roadmap — Phased Delivery

| Phase | Deliverable | Dependencies | Target |
| --- | --- | --- | --- |
| M1 — Foundation | Phase 1–3 pipeline operational; 1,800 TCs enriched; review dashboard; Jira push | Anthropic API key; IGEL KB markdown output complete | Week 1–3 |
| M2 — Validation | Phase 4 domain validation (registry key corpus, path registry, G4+G5 gates); validation UI in dashboard | Registry key extraction from KB complete | Week 4–5 |
| M3 — Scripts | Phase 5 Claude Code script generation; CLAUDE.md and Skills configured; G6 gate; Bitbucket PR flow | Framework code access; conftest.py and fixture inventory | Week 6–8 |
| M4 — Live context | Jira MCP activated (QCAPPS-* format examples); Confluence MCP activated (Apps Testing space) | IGEL provides Jira + Confluence API credentials | Week 9–10 |
| M5 — Scale | Redis task queue for parallel workers; 5,000+ TC run; cross-encoder re-ranker; HNSW index upgrade | M1–M4 stable and validated | Week 11–14 |
| M6 — Feedback loop | Human correction data fed back into KB; fine-tuned re-ranker on IGEL query-passage pairs; automated nightly run | 200+ human-reviewed TCs accumulated | Week 15+ |

## 12.2 Open Items Requiring IGEL Input

| Item | Why Needed | Owner | Priority |
| --- | --- | --- | --- |
| Jira API credentials (JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN) | Activates Jira MCP for format examples + feature/bug context. Critical for TC format accuracy. | IGEL IT / Jira admin | P1 — blocks M4 |
| Confluence API credentials (CONFLUENCE_BASE_URL, CONFLUENCE_API_TOKEN, CONFLUENCE_SPACE_KEY) | Real-time app release notes, updated TC Setup paths, latest registry key changes. | IGEL IT / Confluence admin | P1 — blocks M4 |
| Framework codebase access (Bitbucket read access) | Phase 5 agent reads actual conftest.py, fixture files, helper modules. Without this, scripts use invented fixture names. | IGEL Engineering | P1 — blocks M3 |
| Registry key corpus validation | QA team to confirm the extracted registry key list from KB is complete and accurate before G4 goes live. | IGEL QA Lead | P2 — blocks G4 activation |
| TC Setup path registry validation | QA team to confirm extracted navigation paths are correct for current OS12 version. | IGEL QA Lead | P2 — blocks G4 activation |
| Test lab access for script dry-run | Phase 5 G6 gate runs pytest --collect-only in CI — needs a sandbox UMS + IGEL device or mock. | IGEL Lab / DevOps | P3 — enhances G6 |

# 13\. Appendix — Technology Stack & Configuration

## 13.1 Full Technology Stack

| Component | Technology | Version | License / Cost |
| --- | --- | --- | --- |
| Primary LLM | Claude claude-sonnet-4-20250514 (Anthropic API) | Latest | Usage-based: ~$3/Mtok input, $15/Mtok output |
| Embedding model | text-embedding-3-large (Azure OpenAI) | Latest | Usage-based: ~$0.13/Mtok |
| Image Vision | Claude claude-sonnet-4-20250514 Vision or GPT-4.1 Vision | Latest | Usage-based |
| Vector database | PostgreSQL 17 + pgvector extension | 17.x / 0.7.x | Open source |
| Agent framework | Claude Code (Anthropic) | Latest | Included with API access |
| Task queue | Redis + Celery (Phase 5 scale) | 7.x / 5.x | Open source |
| CI/CD | TeamCity + Bitbucket | Existing | IGEL licensed |
| PDF parsing | PyMuPDF (fitz) + marker-pdf | Latest | Open source / AGPL |
| Docx parsing | python-docx | Latest | MIT |
| HTTP client | httpx (async) + requests | Latest | Open source |
| Monitoring | structlog + Prometheus + Grafana | Latest | Open source |

## 13.2 Required Environment Variables

| Variable | Phase | Description |
| --- | --- | --- |
| ANTHROPIC_API_KEY | 3, 5 | Anthropic API key for Claude generation |
| AZURE_OPENAI_API_KEY | 1, 2 | Azure OpenAI API key for text-embedding-3-large |
| AZURE_OPENAI_ENDPOINT | 1, 2 | Azure OpenAI endpoint URL |
| POSTGRES_HOST | 1, 2, 4 | PostgreSQL host (localhost or remote) |
| POSTGRES_DB | 1, 2, 4 | Database name (igel_kb) |
| POSTGRES_USER | 1, 2, 4 | PostgreSQL username |
| POSTGRES_PASSWORD | 1, 2, 4 | PostgreSQL password (store in TeamCity secure) |
| JIRA_BASE_URL | 7 | Atlassian Jira base URL |
| JIRA_USER_EMAIL | 7 | Jira account email |
| JIRA_API_TOKEN | 7 | Jira API token |
| CONFLUENCE_BASE_URL | 2 (M4) | Confluence base URL |
| CONFLUENCE_API_TOKEN | 2 (M4) | Confluence API token |

_End of Document — IGEL AI Test Generation Hybrid Architecture v2.0_