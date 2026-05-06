# IGEL AI Test Generation — Hybrid Architecture v3.1
### Intelligent Hybrid System (RAG + Knowledge Graph + Learning)

---

## 1. Executive Summary

This document defines **Hybrid Architecture v3.1**, an evolution of v3.0 that integrates:

- **RAG (Retrieval-Augmented Generation)** → factual grounding
- **Knowledge Graph (KG)** → relationship & reasoning layer
- **Feedback Learning System** → continuous improvement
- **Execution Intelligence** → real-world validation feedback

This transforms the system from a **generation pipeline** into a **reasoning-driven test intelligence platform**.

---

## 2. Core Philosophy

| Layer | Purpose |
|------|--------|
| RAG | Retrieve accurate knowledge (documents, chunks, images) |
| Knowledge Graph | Model relationships & workflows |
| LLM | Generate structured outputs |
| Validation | Ensure correctness |
| Feedback Loop | Improve continuously |

---

## 3. High-Level Architecture (v3.1)

```
[Docs / Jira / Confluence / Execution Logs]
        |
PHASE 0 — Feedback Learning Layer
        |
PHASE 1 — Ingestion & KG Extraction
        |
PHASE 2 — Hybrid Retrieval (RAG + KG)
        |
PHASE 3 — Context Fusion Engine
        |
PHASE 4 — Test Case Generation
        |
PHASE 5 — Validation Layer
        |
PHASE 6 — Script Generation
        |
PHASE 7 — Execution Feedback Loop
        |
PHASE 8 — Coverage Intelligence
        |
PHASE 9 — Human Review
        |
PHASE 10 — Publish
```

---

## 4. Phase Enhancements

---

## 4.1 Phase 1 — Ingestion + Knowledge Graph Construction

### Existing (v2)
- Parse → Chunk → Embed

### New (v3.1)

#### Knowledge Graph Extraction
From documents extract:

**Entities:**
- Feature (Zoom SSO)
- Registry Key (app.zoom.global.sso_enabled)
- UI Path (TC Setup > Apps > Zoom > Settings)
- API Endpoint (/umsapi/v3/...)
- Version

**Relationships:**
- Feature → uses → Registry Key
- Feature → configured via → UI Path
- Feature → calls → API
- Feature → depends on → Feature

#### Storage Options
- Neo4j (recommended)
- PostgreSQL (JSONB + edges table)

---

## 4.2 Phase 2 — Hybrid Retrieval Engine (RAG + KG)

### Step 1: Query Understanding
Classify query:
- Exact (registry key)
- Semantic (feature behavior)
- Workflow (multi-step)

---

### Step 2: RAG Retrieval
- Vector search (pgvector)
- BM25 search
- RRF fusion

---

### Step 3: Knowledge Graph Retrieval
- Fetch related nodes
- Expand relationships (1–2 hops)

Example:
Query: "Zoom SSO login"

KG returns:
- Feature → Zoom SSO
- Registry Keys
- UI paths
- Dependencies (Entra ID)

---

### Step 4: Cross-Encoder Re-ranking
- Re-rank combined results
- Improve precision

---

## 4.3 Phase 3 — Context Fusion Engine (NEW)

Combine:
- RAG chunks
- KG relationships
- Image intelligence

Output:
- Structured context block

```
Feature: Zoom SSO
Registry Keys: ...
UI Paths: ...
Dependencies: ...
Known Issues: ...
```

---

## 4.4 Phase 4 — Test Case Generation

Enhancement:
- KG-aware generation

LLM now receives:
- facts (RAG)
- relationships (KG)

Result:
- No hallucinated paths
- Better step ordering

---

## 4.5 Phase 5 — Validation Layer

### Existing Gates
- G1–G7 (unchanged)

### New Gates

#### G8 — Coverage Validation
- Feature has enough test scenarios

#### G9 — Graph Consistency
- All steps align with KG relationships

---

## 4.6 Phase 6 — Script Generation

Enhancement:
- KG → framework mapping

Example:
- API node → actual helper function

---

## 4.7 Phase 7 — Execution Feedback Loop

Inputs:
- Pytest failures
- Logs

Processing:
- Map failure → test step
- Identify patterns

Outputs:
- Fix suggestions
- Learning signals

---

## 4.8 Phase 8 — Coverage Intelligence Engine

Uses KG heavily:

### Capabilities:
- Feature → Test mapping
- Missing scenario detection
- Duplicate detection
- Risk-based prioritization

---

## 5. Feedback Learning System

### Inputs:
- Human edits
- Rejections
- Execution failures

### Storage:
`kb_feedback`

### Outputs:
- Prompt tuning
- Retrieval tuning
- Auto-repair templates

---

## 6. Cost Optimization Layer

### Improvements:
- Context compression (KG reduces token need)
- Smart chunk selection
- Caching frequent queries

Expected reduction: **30–50% tokens**

---

## 7. Data Model (Extended)

### Tables:

#### kb_feedback
- feedback_id
- issue_type
- correction

#### knowledge_graph_nodes
- id
- type
- value

#### knowledge_graph_edges
- source
- relation
- target

#### feature_coverage
- feature
- coverage_score

---

## 8. Workflow Evolution

### v2:
Generate → Validate → Review

### v3.1:
Learn → Retrieve → Reason → Generate → Validate → Execute → Learn

---

## 9. Expected Outcomes

| Metric | v2 | v3.1 Target |
|------|----|------------|
| Accuracy | ~90% | 96%+ |
| Script Success | ~85% | 93%+ |
| Hallucination | Medium | Very Low |
| Coverage Visibility | None | Full |
| Token Cost | High | Reduced |

---

## 10. Implementation Roadmap

### Phase 1
- Knowledge Graph MVP
- Query classification

### Phase 2
- GraphRAG integration
- Cross-encoder reranker

### Phase 3
- Coverage engine
- Execution feedback

---

## 11. Final Summary

Hybrid v3.1 =

**RAG + Knowledge Graph + Validation + Feedback + Execution Intelligence**

This creates a system that is:
- Context-aware (RAG)
- Relationship-aware (KG)
- Self-improving (Feedback)
- Execution-aware (Runtime)

👉 Result: A true **AI-driven testing intelligence platform**, not just a generator.

---

**End of Document**