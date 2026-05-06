# IGEL AI-Powered Test Case & Test Script Generation — Technical Approach

**Prepared by:** Innominds QA Automation Team  
**Date:** May 2026  
**Version:** 1.0  
**Audience:** IGEL Technology — QA & Engineering Leadership

## Table of Contents

1\. Executive Summary

2\. Problem Statement

3\. Solution Architecture Overview

4\. Knowledge Base — Ingestion Pipeline

5\. Vector Store — PostgreSQL + pgvector

6\. Image Intelligence Pipeline

7\. Hybrid Retrieval — How We Find the Right Context

8\. MCP Integrations — Jira, Confluence & PostgreSQL

9\. Test Case Generation — LLM Orchestration

10\. Test Script Generation — Executable Automation Code

11\. Quality Gates & Validation

12\. Current Knowledge Base Statistics

13\. Permissions Required from IGEL

14\. Roadmap & Open Items

15\. Appendix — Technology Stack

## 1\. Executive Summary

Innominds has built an AI-powered test generation system specifically designed for IGEL OS 12, UMS, ICG, IMI, and COSMOS products. The system ingests IGEL's internal and public documentation into a structured knowledge base, retrieves the most relevant context for any given test topic, and generates two artifacts:

1\. **JIRA-format test case documents** — matching the exact QCAPPS-\* format used in IGEL's internal Zephyr/JIRA system, with full step-by-step procedures, TC Setup navigation paths, registry keys, CLI commands, and expected results.

2\. **Executable pytest scripts** — ready-to-run automation code that uses the existing IGEL automation framework (UMS REST API, SSH, OCR-based UI validation) with no placeholder text or human edits required.

The core philosophy: **the richer and more accurate the retrieved context, the higher the fidelity of both the test case document and the executable script.** Every architectural decision — from parent-child chunk hierarchies to image intelligence to Jira/Confluence integration — serves the goal of maximizing context accuracy.

## 2\. Problem Statement

| Challenge | Impact |
| --- | --- |
| IGEL documentation is spread across PDFs, Word documents, Confluence pages, and Jira tickets | Engineers spend hours gathering context before writing a test |
| Test cases written from memory or partial context produce flaky or incomplete steps | Execution failures, missed edge cases, wrong expected results |
| Manually written pytest scripts depend on individual engineers knowing the full framework API | Inconsistent patterns, non-reusable code, onboarding overhead |
| New app versions bring updated configuration paths and registry keys | Previously written tests become stale without systematic updates |
| IGEL product complexity (UMS + IGEL OS + ICG + IMI + COSMOS + SSO providers) is very high | No single engineer holds complete knowledge across all modules |

The AI system addresses all of these by treating IGEL's documentation corpus as a living, queryable knowledge base that feeds every test generation request.

## 3\. Solution Architecture Overview

  
┌─────────────────────────────────────────────────────────────────────────┐  
│ IGEL KNOWLEDGE SOURCES │  
│ │  
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │  
│ │ IGEL Public │ │ Curated │ │ Jira │ │ Confluence │ │  
│ │ Docs (PDFs, │ │ Internal │ │ QCAPPS-\* │ │ Apps │ │  
│ │ Word, CSV) │ │ Test Cases │ │ Tickets │ │ Testing │ │  
│ │ 81 docs │ │ Guides │ │ (pending) │ │ Space │ │  
│ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────┬──────┘ │  
└─────────│────────────────│────────────────│───────────────────│─────────┘  
│ │ │ │  
▼ ▼ ▼ ▼  
┌─────────────────────────────────────────────────────────────────────────┐  
│ INGESTION PIPELINE │  
│ │  
│ Parse → Clean → Chunk (Parent+Child) → Embed → Deduplicate → Store │  
│ │  
│ For Images: Extract → Filter (recurring/irrelevant) → │  
│ GPT-4.1 Vision → Describe + OCR → Embed → Store │  
└────────────────────────────┬────────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────────────┐  
│ POSTGRESQL 17 + pgvector KNOWLEDGE BASE │  
│ │  
│ kb\_documents kb\_parent\_chunks kb\_chunks kb\_images │  
│ (81 docs) (8,250 sections) (53,123 units) (363+ images) │  
│ │  
│ 3072-dim embeddings (text-embedding-3-large) + Full-Text Search index │  
└────────────────────────────┬────────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────────────┐  
│ HYBRID RETRIEVAL ENGINE (per query) │  
│ │  
│ Vector Search (pgvector cosine) + Full-Text Search (tsquery BM25) │  
│ └──────────────────────┘ │  
│ Reciprocal Rank Fusion (RRF, k=60) │  
│ Deduplicate by parent → Fetch full parent sections │  
│ Inline image context from kb\_images │  
└────────────────────────────┬────────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────────────┐  
│ LLM ORCHESTRATION (Azure GPT-4.1) │  
│ │  
│ Pass 1: Generate JIRA-format Markdown test case (4,096 tokens) │  
│ Pass 2: Generate executable pytest script from Pass 1 + repo context │  
└─────────────────────────────────────────────────────────────────────────┘  

## 4\. Knowledge Base — Ingestion Pipeline

### 4.1 Document Sources

The knowledge base is built from three categories of source material:

**Category A — IGEL Public Documentation (structured)**

*   IGEL OS Base System release notes and user guides (PDF)
*   UMS 12.x administrator guide (PDF, 400+ pages)
*   IGEL Cloud Gateway (ICG) technical documentation (PDF)
*   IGEL Management Interface (IMI) API guide (PDF)
*   IGEL Apps guide covering Zoom, Citrix, Teams, Chromium, Firefox, RDP, AVD, Horizon (PDF)
*   Hardware compatibility guide (PDF)
*   Feature-specific how-to guides (Word .doc)

**Category B — Curated Internal Material**

*   Historical test case templates and test plan documents (CSV, Markdown, Word)
*   Defect reports with reproduction steps (CSV)
*   Quick-start testing guides written by the QA team
*   Release notes with new features and known issues

**Category C — Live Integrations (pending IGEL access)**

*   Jira QCAPPS-\* test case tickets (exact format reference + step templates)
*   Jira APPS-\* feature and bug tickets (New Features / Known Issues sections)
*   Confluence "Apps Testing" space (updated procedures, TC Setup paths, changelogs)

### 4.2 Parsing Strategy

Each file type uses a dedicated parser:

| Format | Parser | What is extracted |
| --- | --- | --- |
| PDF | PyMuPDF (fitz) | Text blocks by page, embedded images with bounding boxes, surrounding text context |
| DOCX | python-docx | Paragraphs, tables as structured rows, embedded images |
| DOC (legacy) | Microsoft Word COM (Win) | Converted to DOCX, then same as above |
| CSV | pandas | Row-by-row with column headers as context |
| Markdown | markdown-it-py | Section headers, code blocks, tables |
| MHT | html.parser | Extracted HTML content, stripped to plain text |

Tables are treated specially: each row is serialized with its column headers to preserve the tabular meaning (e.g., Registry Key: app.zoom.global.keep\_login\_data | Type: boolean | Default: false).

### 4.3 Hierarchical Chunking — Parent + Child Architecture

This is one of the most important design decisions in the system.

**The problem with flat chunking:** A single chunk of 150-200 tokens gives the LLM too little context to generate meaningful test steps. But a chunk of 1,500 tokens is too large to index accurately — the embedding becomes an average of too many concepts, degrading retrieval precision.

**Our solution — two-level hierarchy:**

  
PARENT CHUNK (800-1,200 tokens) — returned as context to the LLM  
│ Full section text: "Zoom Desktop Client — Login Methods"  
│ Contains: all login options, registry keys, TC Setup paths,  
│ behavioral descriptions, version notes  
│  
└── CHILD CHUNK 1 (150-300 tokens) — indexed for search  
│ "SSO login with Entra ID is enabled via the registry key  
│ app.zoom.global.sso\_enabled = true. Navigate to TC Setup >  
│ Apps > Zoom > Settings > SSO."  
│  
└── CHILD CHUNK 2 (150-300 tokens) — indexed for search  
│ "Clear Login Data setting removes stored credentials on next  
│ launch. Registry key: app.zoom.global.keep\_login\_data = false."  
│  
└── CHILD CHUNK 3 (150-300 tokens) — indexed for search  
"Known issue: Zoom 6.2.x keeps users signed in even when  
keep\_login\_data is set to false on ARM-based devices."  

**How retrieval uses this:**

1\. The **child chunks** are searched (small = precise match to query intent)

2\. The matched children identify which **parent section** they belong to

3\. The **full parent section** is fetched and passed to the LLM as context

This gives the LLM the complete picture (registry keys, navigation paths, edge cases) while keeping the search index precise. The LLM never works from fragments.

### 4.4 Embedding Model

All text (child chunks + image descriptions) is embedded using **Azure text-embedding-3-large** producing **3,072-dimensional vectors**. This is the highest-quality publicly available embedding model as of 2026, with strong semantic understanding of technical content.

## 5\. Vector Store — PostgreSQL + pgvector

### 5.1 Why PostgreSQL Instead of a Dedicated Vector DB

We chose PostgreSQL 17 with the pgvector extension over dedicated vector databases (Pinecone, Weaviate, Chroma) for the following reasons:

| Factor | PostgreSQL + pgvector | Dedicated Vector DB |
| --- | --- | --- |
| Full-text search | Native (tsvector/tsquery) | Requires separate stack |
| Relational joins | Native (docs → chunks → images) | Not available |
| ACID transactions | Full | Limited |
| Operational complexity | Single database | Two databases to manage |
| SQL familiarity | Universal | Proprietary query language |
| Filtering by product/file_type | Standard WHERE clause | Metadata filtering varies |

The key advantage is **hybrid search in a single query**: we can combine pgvector cosine similarity with PostgreSQL full-text search (BM25 approximation) and filter by product, chunk type, or document in a single SQL query.

### 5.2 Schema Design

  
\-- Source document registry  
kb\_documents  
id UUID, file\_name TEXT, file\_path TEXT, file\_type TEXT,  
file\_hash TEXT UNIQUE, -- prevents re-ingestion of unchanged files  
product TEXT, -- "IGEL OS" | "UMS" | "ICG" | "IMI" | "COSMOS"  
total\_parent\_chunks INT, total\_chunks INT,  
metadata JSONB -- version, source\_url, ingested\_by, etc.  
  
\-- Full sections (800-1,200 tokens) — LLM context window content  
kb\_parent\_chunks  
id UUID, document\_id UUID → kb\_documents,  
chunk\_index INT, content TEXT,  
section\_title TEXT, -- "Chapter 4: SSO Configuration"  
chunk\_type TEXT, -- "procedure" | "concept" | "configuration" | "table"  
page\_number INT  
  
\-- Search index units (150-300 tokens) — what gets embedded and searched  
kb\_chunks  
id UUID, parent\_chunk\_id UUID → kb\_parent\_chunks, document\_id UUID,  
content TEXT,  
embedding VECTOR(3072), -- pgvector column  
tsvector\_content TSVECTOR -- GIN index for full-text search  
  
\-- Image intelligence store  
kb\_images  
id UUID, document\_id UUID, parent\_chunk\_id UUID,  
sequence\_index INT, page\_number INT,  
image\_hash TEXT, -- SHA-256 for global deduplication  
image\_bytes BYTEA,  
image\_type TEXT, -- "ui\_screenshot" | "configuration\_dialog" | "architecture\_diagram"  
verbatim\_text TEXT, -- exact OCR output from GPT-4.1 Vision  
ui\_elements JSONB, -- \[{type, label, state, value}, ...\]  
semantic\_description TEXT,  
test\_relevance TEXT, -- concrete test actions derived from image  
description\_embedding VECTOR(3072)  

### 5.3 Indexes

  
CREATE INDEX kb\_chunks\_embedding\_idx ON kb\_chunks  
USING ivfflat (embedding vector\_cosine\_ops) WITH (lists = 100);  
  
CREATE INDEX kb\_chunks\_fts\_idx ON kb\_chunks  
USING GIN (tsvector\_content);  
  
CREATE INDEX kb\_images\_embedding\_idx ON kb\_images  
USING ivfflat (description\_embedding vector\_cosine\_ops) WITH (lists = 50);  
  
CREATE UNIQUE INDEX kb\_images\_hash\_idx ON kb\_images (image\_hash);  

## 6\. Image Intelligence Pipeline

### 6.1 Why Images Matter for Test Generation

IGEL's technical documentation is heavily visual. Configuration dialogs, UMS Web UI screenshots, registry navigation trees, network architecture diagrams — these images often contain:

*   **Exact UI element labels** that must be referenced in test steps ("Click the _Apply to all devices_ button")
*   **Registry key paths** visible in UMS Registry Editor screenshots
*   **TC Setup navigation paths** shown step-by-step in annotated screenshots
*   **Error messages** showing exact text QA engineers need to verify
*   **Before/after states** that define expected results

If images are ignored, these critical details are lost. A test case generated without image context may use approximate navigation paths or miss a required checkbox entirely.

### 6.2 Extraction

  
PDF/DOCX File  
│  
▼ PyMuPDF / python-docx  
Embedded Images (raw bytes + page number + bounding box + surrounding text)  
│  
▼ Recurring Image Detection  
Is this image a header/logo/watermark appearing on >25% of pages?  
YES → Skip entirely (no Vision API call, no DB storage)  
NO → Continue  
│  
▼ Global Hash Deduplication  
Does SHA-256(image\_bytes) already exist in kb\_images from ANY document?  
YES → Skip (same diagram already described in another document)  
NO → Continue  
│  
▼ GPT-4.1 Vision API  

### 6.3 GPT-4.1 Vision Analysis

Each image is sent to GPT-4.1 Vision with:

*   The source document name and section title (so the model understands context)
*   The surrounding text (up to 4,000 characters from the adjacent paragraphs)
*   The page number and any caption found near the image

The model returns a structured JSON:

  
{  
"image\_type": "configuration\_dialog",  
"verbatim\_text": "Allow Saving Credentials\\nEnabled\\nNever\\nAlways\\nAsk user each time\\nOK Cancel",  
"ui\_elements": \[  
{"type": "dropdown", "label": "Allow Saving Credentials", "state": "expanded", "value": "Enabled"},  
{"type": "button", "label": "OK", "state": "enabled", "value": null},  
{"type": "button", "label": "Cancel", "state": "enabled", "value": null}  
\],  
"semantic\_description": "This is the IGEL UMS Registry configuration dialog for enabling permanent storage of Wi-Fi credentials. The dropdown controls whether users can save network passwords. Located under Sessions > Network > WLAN > Security > Allow Saving Credentials.",  
"test\_relevance": "Verify 'Allow Saving Credentials' dropdown is present at the correct registry path.\\nCheck that selecting 'Enabled' shows the save prompt on Wi-Fi login.\\nVerify that selecting 'Never' prevents credential storage even when user checks 'Save'."  
}  

### 6.4 IGEL Relevance Filter

After Vision analysis, a second filter runs before storage:

  
Is image\_type in {icon\_or\_logo, recurring\_header\_or\_logo}? → Skip  
Does test\_relevance start with "Reference image only"?  
AND verbatim\_text is empty or "NONE"?  
AND ui\_elements is empty?  
→ Skip (purely decorative, zero test value)  
Otherwise → Store with full embedding  

This ensures only images with extractable test intelligence are stored.

### 6.5 Image Embedding and Retrieval

The combined embedding text for each image is:

  
\[Image from: IGEL Apps.pdf\]  
Section: Zoom Desktop Client — Login Configuration  
Page: 47  
Type: configuration\_dialog  
  
Visible text in image:  
Clear Login Data  
Keep me signed in  
Enabled Disabled  
  
Description:  
This dialog shows the Zoom Desktop Client login persistence settings in the  
IGEL setup wizard. The 'Clear Login Data' toggle controls whether Zoom  
retains user credentials across sessions.  
  
Test relevance:  
Verify Clear Login Data toggle appears under TC Setup > Apps > Zoom > Settings.  
Check that enabling Clear Login Data removes stored credentials on next launch.  
Verify Keep me signed in checkbox state persists after device reboot.  
  
Surrounding document context:  
The registry key app.zoom.global.keep\_login\_data controls this behavior...  

This rich text is embedded and indexed. When a QA engineer asks for "Zoom login methods", the image embedding will surface alongside the text chunks, injecting the visual UI details into the generation context.

### 6.6 Current Image Statistics

| Image Type | Count |
| --- | --- |
| UI Screenshot | 193 |
| Configuration Dialog | 123 |
| Architecture Diagram | 15 |
| Photo | 11 |
| Unknown | 7 |
| Code Snippet | 5 |
| Error Message | 3 |
| Screenshot with Annotations | 1 |
| Flowchart | 1 |
| Total | 363+ (ingestion ongoing) |

## 7\. Hybrid Retrieval — How We Find the Right Context

### 7.1 The Problem with Vector-Only Search

Pure vector search fails for IGEL content in specific ways:

*   Query: "app.zoom.global.keep\_login\_data" — an exact registry key
    *   Vector search finds semantically similar content but may miss the exact key
    *   Full-text search finds it exactly (BM25 term matching)
*   Query: "Entra ID SSO login validation" — a semantic concept
    *   Full-text search may miss if the document says "Microsoft Azure AD" or "OIDC provider"
    *   Vector search finds it (semantic similarity regardless of exact terminology)

Neither alone is sufficient. The hybrid approach captures both.

### 7.2 Retrieval Pipeline

  
User Query: "Zoom Desktop Client Clear Login Data setting"  
│  
▼  
Step 1 — Embed query (text-embedding-3-large → 3072-dim vector)  
│  
├─── Step 2a — Vector search (pgvector cosine)  
│ SELECT parent\_chunk\_id, 1 - (embedding <=> query\_vec) AS score  
│ FROM kb\_chunks ORDER BY embedding <=> query\_vec LIMIT 32  
│ → Returns: \[chunk\_A rank 1, chunk\_B rank 2, chunk\_C rank 3, ...\]  
│  
└─── Step 2b — Full-text search (PostgreSQL plainto\_tsquery)  
SELECT parent\_chunk\_id, ts\_rank(tsvector\_content, query) AS score  
FROM kb\_chunks WHERE tsvector\_content @@ plainto\_tsquery('english', query)  
ORDER BY score DESC LIMIT 32  
→ Returns: \[chunk\_D rank 1, chunk\_A rank 2, chunk\_E rank 3, ...\]  
│  
▼  
Step 3 — Reciprocal Rank Fusion (RRF, k=60)  
RRF\_score(chunk) = Σ 1/(k + rank\_in\_list)  
Combined ranking merges both result lists, rewarding chunks that  
rank well in BOTH searches (high confidence results)  
│  
▼  
Step 4 — Deduplicate by parent\_chunk\_id  
If multiple child chunks point to the same parent section, keep only  
the highest-scoring one → prevents the same section being used twice  
│  
▼  
Step 5 — Fetch full parent content  
SELECT content FROM kb\_parent\_chunks WHERE id IN (top\_k parent ids)  
→ Returns full 800-1,200 token sections with all registry keys,  
navigation paths, and behavioral details  
│  
▼  
Step 6 — Inline image context  
For each parent chunk, fetch related images from kb\_images  
WHERE parent\_chunk\_id = ? AND image\_type NOT IN (recurring\_header\_or\_logo)  
→ Appends image descriptions, OCR text, and test hints to the context  
│  
▼  
Context Window: 8 parent sections + image descriptions → ~5,000-6,000 tokens  
Passed to GPT-4.1 for test case generation  

### 7.3 Re-Ranking (Current and Planned)

**Current:** RRF is our fusion mechanism. It is a well-established re-ranking approach that consistently outperforms either single-signal retrieval.

**Planned enhancement:** A dedicated cross-encoder re-ranker (e.g., a fine-tuned ms-marco-MiniLM-L-6-v2 or Cohere Rerank API) applied as a final step after RRF. Cross-encoders re-score each (query, passage) pair jointly — dramatically improving precision for complex, multi-concept queries like "Zoom 6.3 login methods on AMD devices with SSO enabled". This is on the roadmap and will be introduced once we have sufficient query-passage relevance feedback from real usage.

## 8\. MCP Integrations — Jira, Confluence & PostgreSQL

MCP (Model Context Protocol) is the interface layer between our retrieval sources and the LLM. Each source is wrapped as an MCP that the orchestrator can call before assembling the final prompt.

### 8.1 PostgreSQL MCP (Active)

The PostgreSQL MCP is the primary retrieval source. It is fully implemented and active.

**Capabilities:**

*   search(query, product, top\_k) — hybrid vector+FTS retrieval with RRF
*   \_fetch\_image\_context(parent\_chunk\_id) — inline image descriptions per section
*   search\_images(query, top\_k) — direct vector search on image embeddings
*   get\_context\_block(results, token\_budget) — formats results into LLM-ready context string with token budget management

**What it returns per result:**

  
MCPSearchResult(  
child\_chunk\_id, parent\_chunk\_id, document\_id,  
child\_content, # what matched the query  
parent\_content, # full section (800-1,200 tokens) sent to LLM  
section\_title, file\_name, product, chunk\_type,  
rrf\_score, # fusion score  
image\_context = \[ # images from same section  
{image\_type, verbatim\_text, semantic\_description, test\_relevance, ...}  
\]  
)  

### 8.2 Jira MCP (Implemented — Awaiting IGEL Access)

The Jira MCP is fully written and wired into the pipeline. It is currently disabled (JIRA\_ENABLED=false). Activating it requires IGEL to provide API credentials.

**What it will do:**

_Fetch existing QCAPPS-_ test cases for format reference:\*

  
Query: "Zoom Desktop Client login methods"  
→ JiraMCP searches QCAPPS project for matching test cases  
→ Returns: \[QCAPPS-1249 (Zoom 7.0.0 login), QCAPPS-1183 (Zoom 6.3 SSO), ...\]  
→ Extracts: test steps format, TC Setup navigation paths used, acceptance criteria  
→ Injected into prompt as: "Here are existing IGEL JIRA test cases for this topic..."  

_Fetch APPS-_ feature and bug tickets:\*

  
Query: release version "7.0.0"  
→ JiraMCP searches APPS project for this fixVersion  
→ Returns: \[APPS-4421 "Zoom 7.0.0 New: SSO token refresh", APPS-4389 "Bug: Clear login on ARM"\]  
→ These populate "New Features" and "Known Issues" sections of the test case document  

**Configuration when IGEL provides access:**

  
JIRA\_ENABLED=true  
JIRA\_BASE\_URL=https://igel-jira.atlassian.net  
JIRA\_EMAIL=your-igel-email@igel.com  
JIRA\_API\_TOKEN=your-atlassian-api-token  
JIRA\_PROJECT\_KEY=QCAPPS  

**Why this is critical:** The existing QCAPPS-\* tickets contain IGEL's actual test case format, validated TC Setup paths, and real registry key names. Using them as format examples eliminates hallucination risk — the LLM sees what a real, approved IGEL test case looks like and mirrors it.

### 8.3 Confluence MCP (Implemented — Awaiting IGEL Access)

The Confluence MCP is fully written and wired into the pipeline. It is currently disabled (CONFLUENCE\_ENABLED=false).

**What it will do:**

_Real-time documentation for new app releases:_

  
Zoom Desktop Client 7.2.0 was released last week.  
→ ConfluenceMCP searches "Apps Testing" space for "Zoom 7.2.0"  
→ Returns: release notes page with new settings, changed registry keys,  
updated TC Setup navigation paths  
→ This context is injected alongside the PostgreSQL KB context  

This is essential because the PostgreSQL KB is a snapshot — it reflects documentation at ingestion time. Confluence pages are living documents updated by the IGEL product team. Accessing them in real time means generated test cases reflect the latest product state without requiring a full KB re-ingestion.

_What it extracts from Confluence HTML:_

*   TC Setup navigation paths (regex pattern: TC Setup > ... > ... = value)
*   Registry key names (pattern: app.\[a-z0-9\_\]+.\[a-z0-9\_.\]+)
*   CLI/terminal commands (lines starting with systemctl, journalctl, grep, klist, etc.)
*   "Additional Information" bullet points from page sections

**Configuration when IGEL provides access:**

  
CONFLUENCE\_ENABLED=true  
CONFLUENCE\_BASE\_URL=https://igel-jira.atlassian.net/wiki  
CONFLUENCE\_EMAIL=your-igel-email@igel.com  
CONFLUENCE\_API\_TOKEN=your-atlassian-api-token  
CONFLUENCE\_SPACE\_KEY=APPSTEST  

### 8.4 Context Assembly — All Sources Combined

When all three MCPs are active, the LLM receives a unified context:

  
KNOWLEDGE BASE CONTEXT (PostgreSQL)  
\=====================================  
\=== SOURCE 1: Zoom — Login Methods ===  
Product: IGEL OS | File: IGEL Apps.pdf | Relevance: 0.0312  
\[Full section text: SSO configuration, Clear Login Data, registry keys...\]  
  
\[Related Images:\]  
• Configuration dialog showing Zoom login settings with SSO toggle enabled  
Visible text: "Enable SSO ☑ Clear Login Data ☑ Keep me signed in ☐"  
Test hints: Verify SSO toggle state persists after reboot...  
  
ADDITIONAL CONTEXT (Jira)  
\=====================================  
\[QCAPPS-1249\] Zoom 7.0.0 — Login methods validation  
Description: Validates SSO, email/password, and Google login...  
New Features: \[APPS-4421\] SSO token refresh without re-authentication  
Known Issues: \[APPS-4389\] Clear login data ignored on ARM in 7.0.0  
  
ADDITIONAL CONTEXT (Confluence)  
\=====================================  
\[Zoom 7.0.0 Release Notes — Apps Testing Space\]  
Last updated: 2026-04-15  
TC Setup paths found:  
TC Setup > Apps > Zoom > Settings > Clear Login Data = true  
TC Setup > Apps > Zoom > SSO > Enable SSO = true  
Registry keys: app.zoom.global.keep\_login\_data, app.zoom.global.sso\_enabled  

This is the full richness of context the LLM uses. Each source contributes what it does best: the PostgreSQL KB provides deep technical detail and image intelligence; Jira provides validated format and feature/bug references; Confluence provides the latest changes.

## 9\. Test Case Generation — LLM Orchestration

### 9.1 The IGEL Expert System Prompt

The LLM is given a detailed persona and ruleset before seeing any context:

  
You are a senior IGEL QA automation engineer with deep expertise in testing IGEL products.  
Generate test cases based ONLY on the documentation context provided.  
Never invent steps, settings, or expected values not explicitly present in the context.  
  
IGEL PRODUCT KNOWLEDGE  
\- UMS: REST API on HTTPS port 8443 (https://<ums-ip>:8443/umsapi/v3/)  
\- IGEL OS 12: Linux thin client, SSH on port 22, managed via UMS profiles  
\- ICG: Reverse proxy for cloud-to-device communication without VPN  
\- SSO Providers: Entra ID, Okta, PingOne, Omnissa Horizon  
  
GENERATION RULES  
1\. Use ONLY provided KB context — no invented steps  
2\. All configurable values come from api\_config dict or ums\_cred/device\_cred  
3\. TC Setup navigation paths must be exact (e.g., TC Setup > Apps > Zoom > Settings)  
4\. Registry keys must use actual IGEL key naming (e.g., app.zoom.global.keep\_login\_data)  
5\. Cleanup steps are mandatory — always detach profiles and reboot the device  

This prevents the most common failure modes in LLM-generated test cases: hallucinated settings names, invented navigation paths, and missing cleanup.

### 9.2 JIRA-Format Output (QCAPPS-\* Compatible)

The generated markdown test case matches the format used in IGEL's Zephyr/JIRA system:

  
\# TC011: Entra ID SSO Login Validation  
  
\## Key Details  
  
\*\*Description\*\*  
End-to-end SSO login validation for IGEL OS 12 using Microsoft Entra ID (Azure AD)  
as identity provider. Covers profile assignment via UMS, reboot, VNC login screen  
validation, MFA, Kerberos ticket verification, and cleanup.  
  
\*\*Additional Information\*\*  
\- Entra ID SSO profile must be pre-created in UMS (UMS > Profiles > "Entra-ID-SSO-Profile")  
\- UMS REST API accessed via HTTPS port 8443  
\- Kerberos ticket validated via SSH command: klist  
\- MFA (TOTP) secrets required if MFA is enabled for test user  
  
\*\*New Features\*\*  
\- \[QCL-3139\] Entra ID SSO integration for IGEL OS 12  
\- \[APPS-4421\] SSO token refresh without re-authentication  
  
\*\*Known Issues\*\*  
\- None documented in context  
  
\*\*Acceptance Criteria\*\*  
\- Entra ID login screen appears after profile assignment and reboot  
\- User can log in with valid credentials (with or without MFA)  
\- Kerberos ticket present and valid (klist output verified)  
\- Local login restored after profile removal  
  
\*\*Required Hardware\*\*  
\- IGEL OS 12 device (AMD or Intel)  
\- SSH and VNC/Shadow enabled  
  
\*\*Environment\*\*  
\- IGEL OS 12.7.x+  
  
\*\*Preconditions\*\*  
\- Device registered in UMS, online status confirmed  
\- Entra ID SSO profile exists in UMS  
\- Valid Entra ID test user credentials and OTP secret available  
  
\## TC Setup Option to Change Screenlock/Screensaver Timer  
TC Setup > User Interface > Screenlock/Screensaver > Start automatically = true  
TC Setup > User Interface > Screenlock/Screensaver > Timeout = 1  
  
\## Test Details  
  
| # | STEP | TEST DATA | EXPECTED RESULT |  
|---|------|-----------|-----------------|  
| 1 | \*\*Assign Entra ID SSO profile to device.\*\* | TC Setup > UMS > Devices > \[device\] → Assign "Entra-ID-SSO-Profile" | Profile appears in device's assigned profiles list |  
| 2 | \*\*Trigger device reboot via UMS.\*\* | UMS API: send reboot command; wait for device Online status | Device reboots and returns Online within 90 seconds |  
| 3 | \*\*Verify Entra ID login screen via VNC Shadow.\*\* | Open VNC shadow session; check for Microsoft/Entra ID login UI | Entra ID branding and username input visible |  
| 4 | \*\*Complete login with credentials and MFA.\*\* | Enter test user email + password; generate OTP if prompted | Login succeeds, no auth errors |  
| 5 | \*\*Verify IGEL desktop and user context.\*\* | Observe VNC after login; check for user-specific elements | IGEL desktop loaded, correct user context |  
| 6 | \*\*Verify Kerberos ticket via SSH.\*\* | SSH as root; run: klist | Valid Kerberos ticket for Entra ID user, not expired |  
| 7 | \*\*Unassign profile, reboot, verify local login.\*\* | Detach profile via UMS API; reboot; open VNC session | Local IGEL OS login screen restored, no SSO prompt |  
  
\## Cleanup Steps  
  
| Step | Action | Expected Result |  
|------|--------|-----------------|  
| 1 | Detach Entra ID SSO profile via UMS API | No SSO profile assigned in UMS |  
| 2 | Reboot device via UMS API | Device returns to Online with local login |  

### 9.3 Token Budget Management

The system uses a conservative token budget to stay within GPT-4.1's optimal generation window:

*   Max context budget: 6,000 tokens
*   Reserve for prompt template: 800 tokens
*   Available for KB chunks: 5,200 tokens
*   Chunks are added in descending RRF score order, truncated at word boundary if needed
*   Images are inlined after each chunk's text (capped at 3 images per chunk)

## 10\. Test Script Generation — Executable Automation Code

### 10.1 Two-Pass Generation

**Pass 1 — Markdown test case** (section 9 above): Produces the human-readable JIRA document with full context. This is the "specification" for Pass 2.

**Pass 2 — Python pytest file**: Uses the markdown test case as its primary input. The LLM is told to implement the steps from the markdown document using the IGEL automation framework.

The reason for two passes:

*   Pass 1 forces the LLM to think through the test logic at a high level first
*   Pass 2 has a precise implementation spec to code against
*   This mirrors how human engineers work: write the test case → write the script

### 10.2 Framework Context Injection

Every generated script uses the exact same framework as the existing IGEL automation suite:

  
\# Verbatim import block — never modified  
import time, allure  
import pytest  
from core.api.UMS import UMS  
from core.api.ums\_wums\_api import UMSWUMSApi  
from core.api.auth\_token import UMSAuthTokenService  
from core.ssh.ssh import SSHClient  
from core.ui.ui\_automation\_text import OcrUiInteractor  
from bussiness.page\_login import ums\_login  
from config.read\_config import ums\_cred, device\_cred, otp\_secrets\_cred, root\_path  
from core.ssh.my\_logger import logger  
from bussiness.onepassword\_otp import OTPGenerator  
  
click = OcrUiInteractor()  

Every generated script uses these same classes, same credential dictionaries, same OCR interface. This means generated tests slot directly into the existing test runner with no modification to imports or configuration.

### 10.3 Execution Pattern — What Every Script Looks Like

  
@allure.step("TC011 SN: Assign Entra ID SSO profile to device via UMS API")  
def TC011\_step1(api\_config, browser) -> bool:  
try:  
ums = UMS(ums\_cred\["base\_url"\], ums\_cred\["username"\], ums\_cred\["password"\])  
wums = UMSWUMSApi(ums\_cred\["weburl"\], ums\_cred\["username"\], ums\_cred\["password"\])  
dev = ums.get\_vm\_details(device\_cred\["hostname"\])  
  
\# Assign profile from api\_config (never hardcoded)  
profile = ums.get\_profile\_details(api\_config.get("sso\_profile\_name", "Entra-ID-SSO-Profile"))  
result = wums.assign\_object(dev\["id"\], profile\["id"\], "profile")  
return result is not None  
  
except Exception as e:  
logger.error(f"TC011\_step1: {e}"); return False  
  
  
@allure.feature("SSO Validation")  
@allure.severity(allure.severity\_level.CRITICAL)  
def test\_TC011\_step1(api\_config, browser\_instance): assert TC011\_step1(api\_config, browser\_instance)  

**Key properties enforced in every generated script:**

| Property | Implementation |
| --- | --- |
| No hardcoded credentials | All from ums_cred, device_cred, api_config dicts |
| No hardcoded IPs | ums_cred["base_url"], device_cred["host"] |
| Returns bool | Every step function → return True/False |
| try/except | Every step wrapped; exception logged and returns False |
| Single-line test functions | def test_*(): assert step_func(...) |
| Allure reporting | @allure.step, @allure.feature, @allure.severity decorators |
| Cleanup mandatory | Always ends with a cleanup function that detaches profiles and reboots |

### 10.4 Reusability and Framework Scalability (Roadmap)

**Currently implemented helpers (generated in every script):**

  
def get\_ssh():  
return SSHClient(host=device\_cred\["host"\], user=device\_cred\["user"\],  
pwd=device\_cred\["pwd"\], port=device\_cred\["port"\])  
  
def \_assign(ums, wums, device, profile\_key, default\_name, api\_config):  
profile = ums.get\_profile\_details(api\_config.get(profile\_key, default\_name))  
wums.assign\_object(device\["id"\], profile\["id"\], "profile")  
return profile  
  
def \_detach(ums, wums, device, profile\_key, default\_name, api\_config):  
profile = ums.get\_profile\_details(api\_config.get(profile\_key, default\_name))  
wums.detach\_profile(device\["id"\], profile\["id"\])  

**Planned — Repo Context Analysis:** The next generation phase will include an analysis of the existing tests/Testscript\_10/ directory. The LLM will be shown:

1\. Common patterns already used across existing scripts (e.g., how \_assign() is called, how VNC sessions are initiated, how time.sleep is used for reboot wait loops)

2\. Existing conftest fixtures available for reuse

3\. Shared utility functions in bussiness/ and core/

By injecting this "repo context" into Pass 2, the LLM will:

*   Reuse existing helper functions instead of re-implementing them
*   Follow established wait-for-online patterns rather than inventing new ones
*   Reference existing api\_config.yaml keys correctly
*   Produce scripts that are stylistically consistent with the existing test suite

This moves the "80% executable without human edits" target toward **90-95%**.

## 11\. Quality Gates & Validation

### 11.1 Automatic Validation on Every Generated Script

  
Generated Python content  
│  
▼  
ast.parse(code) ──────── FAIL → saved as filename.py.invalid + warning logged  
│ PASS  
▼  
Check for all 9 required imports ── MISSING → warning appended to result.warnings  
│  
▼  
Check for "TODO", "placeholder", "add here" ── FOUND → warning flagged  
│  
▼  
Saved to tests/Generated/test\_TC{id}\_{slug}.py  

### 11.2 What We Validate Before Delivery

*   Syntax validity (AST parse passes)
*   All required imports present verbatim
*   No hardcoded IPs, passwords, or usernames
*   Every step function returns bool
*   Cleanup step exists
*   TC Setup navigation paths match known IGEL format
*   Registry keys follow IGEL naming convention (app._._)

### 11.3 What Requires Human Review

*   Verify step ordering makes logical sense for the specific feature
*   Validate that api\_config keys referenced exist in testdata/sso/api\_config.yaml
*   Confirm UMS API method names match actual class implementations
*   Test on actual device against the specific app version

## 12\. Current Knowledge Base Statistics

| Metric | Value |
| --- | --- |
| Total source documents | 81 |
| Document types | PDF, DOCX, DOC, CSV, Markdown |
| Parent sections (LLM context units) | 8,250 |
| Child chunks (search index units) | 53,123 |
| Images stored | 363+ (ingestion ongoing) |
| — UI Screenshots | 193 |
| — Configuration Dialogs | 123 |
| — Architecture Diagrams | 15 |
| — Photos | 11 |
| — Code Snippets / Error Messages | 8 |
| Embedding model | text-embedding-3-large (3072d) |
| Vision model | gpt-4.1 (Azure OpenAI) |
| Text generation model | gpt-4.1 (Azure OpenAI) |
| Vector index type | IVFFlat (cosine) |
| Full-text index | PostgreSQL GIN + tsvector |

## 13\. Permissions Required from IGEL

To activate the Jira and Confluence integrations and fully close the context gap, we need the following from IGEL:

### 13.1 Jira API Access

| Requirement | Details |
| --- | --- |
| Access type | Atlassian API token (not password) |
| Account | A service account or existing IGEL QA team member account |
| Jira URL | https://igel-jira.atlassian.net |
| Minimum permissions | Read access to QCAPPS project and APPS project |
| What we will read | Test case summaries, descriptions, step tables, issue links |
| What we will NOT do | Create, modify, or delete any Jira tickets |

**Impact if provided:** The LLM will see real QCAPPS-\* ticket content as format examples, dramatically improving test step precision and ensuring New Features / Known Issues sections are always populated from actual IGEL tickets.

### 13.2 Confluence API Access

| Requirement | Details |
| --- | --- |
| Access type | Atlassian API token (same account as Jira is fine) |
| Confluence URL | https://igel-jira.atlassian.net/wiki |
| Space key | APPSTEST (Apps Testing space) |
| Minimum permissions | Read access to the Apps Testing Confluence space |
| What we will read | Page content: release notes, how-to guides, TC Setup path references |
| What we will NOT do | Create, modify, or delete any Confluence pages |

**Impact if provided:** Generated test cases will always reflect the latest Confluence documentation, even for app versions released after our last KB ingestion. This eliminates the "stale documentation" problem entirely for active test case generation.

### 13.3 Data Handling Commitment

*   All Jira/Confluence content fetched is used **only** for in-context LLM prompt construction
*   No content is stored persistently (unlike the KB documents)
*   Content is fetched per-query and discarded after the generation call
*   If persistent caching is desired (for performance), we can implement time-bounded caching with a configurable TTL (e.g., 24 hours)

## 14\. Roadmap & Open Items

### Phase 1 — Complete (Current State)

*   PostgreSQL KB ingestion pipeline (81 documents)
*   Parent-child hierarchical chunking (8,250 parent / 53,123 child)
*   Image intelligence pipeline (GPT-4.1 Vision, 363+ images)
*   Hybrid retrieval (vector + FTS + RRF)
*   JIRA-format test case generation (QCAPPS-\* compatible)
*   Executable pytest script generation (syntax valid, framework-consistent)
*   MCP stubs for Jira and Confluence (disabled, ready to activate)
*   PostgreSQL MCP (active)

### Phase 2 — In Progress / Next

*   Complete PDF image ingestion for remaining 25 documents
*   Activate Jira MCP (pending IGEL API access)
*   Activate Confluence MCP (pending IGEL API access)
*   Repo context injection — analyze existing tests/Testscript\_10/ for reusable patterns

### Phase 3 — Planned

*   Cross-encoder re-ranker for improved retrieval precision
*   Continuous KB sync — auto-ingest new documents added to the Knowledge Base directory
*   Execution feedback loop — failed test runs report back to flag KB gaps
*   Test coverage map — dashboard showing which product features have test coverage
*   Multi-device matrix — auto-generate AMD and Intel variants of the same test case
*   Fine-tuned embedding model — domain-specific embeddings trained on IGEL terminology

### Known Limitations

| Limitation | Current Workaround | Long-term Solution |
| --- | --- | --- |
| .doc images require Microsoft Word COM | Skip .doc image extraction; text content still fully ingested | Convert all .doc to .docx once |
| KB is a point-in-time snapshot | Manual re-ingestion when docs updated | Confluence MCP provides real-time updates |
| 4 legacy recurring_header_or_logo images in DB | Non-functional — filtered out at retrieval time | One-time cleanup query |
| No fine-tuned re-ranker yet | RRF provides good but not optimal ranking | Phase 3 cross-encoder |

## 15\. Appendix — Technology Stack

| Component | Technology | Version | Purpose |
| --- | --- | --- | --- |
| Vector Database | PostgreSQL + pgvector | 17.x | Storage and hybrid search |
| Embedding Model | Azure text-embedding-3-large | 2024-02 | 3072-dim semantic vectors |
| Vision Model | Azure GPT-4.1 | 2024-12 preview | Image analysis and OCR |
| Text Generation | Azure GPT-4.1 | 2024-12 preview | Test case and script generation |
| PDF Parsing | PyMuPDF (fitz) | 1.27.x | Image + text extraction from PDFs |
| DOCX Parsing | python-docx | 1.1.x | Word document parsing |
| Ingestion Framework | Python 3.12 | Custom | Document pipeline |
| Test Framework | pytest + Allure | Latest | Generated test execution |
| UMS Automation | IGEL UMS REST API | v3 | Device and profile management |
| SSH Automation | Paramiko | 3.x | Device shell command execution |
| OCR UI Validation | Doctr + PyAutoGUI | Custom | Screen-based verification |
| Jira Integration | atlassian-python-api | 3.x | QCAPPS/APPS ticket access |
| Confluence Integration | atlassian-python-api | 3.x | Documentation page access |
| Retry/Resilience | tenacity | 8.x | API call retry with backoff |
| CLI Interface | argparse + Rich | Python stdlib | Generation and ingestion CLI |

_Document prepared by Innominds QA Automation Team_