# System Architecture — Balbird Intelligence

## 1. Architectural Principles

Balbird Intelligence is designed as an **intelligence and business coordination layer** on top of existing business operations.

```
Outlook Emails + SO/MRP Reference Data
              │
              ▼
   Data Ingestion & Preprocessing
              │
              ▼
     AI Intelligence Engine
 (Domain, Intent, Priority, Entities, Deadlines, Actions)
              │
              ▼
    Business Context Engine
 (Multi-signal Case Matching & Linking)
              │
              ▼
     Business Cases & Tasks
(Task Proposals -> Human Approval -> Legacy tasks table)
              │
              ▼
   Dependency & Blocker Graph
              │
              ▼
   Monitoring & Risk Engine
(Shortages, Overdue, Blockers, Inactivity)
              │
              ▼
   Smart Drafts & Dashboards
```

---

## 2. Component Architecture

### A. Ingestion Layer
- **FixtureEmailProvider:** Safe synthetic email ingestion from `.json` and `.eml` files without live network requirements.
- **EmailPreprocessor:** Cleans line endings, separates authored message body from historical quoted replies, identifies automated senders and signatures, and produces SHA-256 content hashes for idempotency.
- **WorkbookParser:** OpenPyXL / Pandas loader for SO registers and MRP spreadsheets.

### B. AI Intelligence Layer
- **AIProvider Protocol:** Strict abstraction layer decoupling business services from inference vendors.
- **MockAIProvider:** Deterministic local classifier and extractor for test suites, offline development, and CI.
- **OpenRouterAIProvider:** OpenAI-compatible client featuring daily and per-minute request gating, token budgeting, exponential backoff with jitter, and structured JSON schema validation.

### C. Convergence & Context Engine
- Links disparate emails, customers, suppliers, parts, and Sales Orders into unified `bi_business_cases`.
- Prioritizes exact references (`SO-1025`, `HT-2045`) over heuristic subject similarity.
- Ambigous matches route to `bi_review_queue`.

### D. Task Intelligence & Task Orch Integration
- AI actions are stored as **proposals** in `bi_task_proposals`.
- Upon human approval, records are written to the authoritative legacy `tasks` table (`task_id` formatted as `TEXT`).
- Detailed provenance is preserved in `bi_task_metadata` and `bi_task_sources`.

### E. Dependency & Risk Engine
- Directed acyclic graph (DAG) representation of dependencies (`bi_dependencies`).
- Depth-first search (DFS) cycle detection rejects circular dependencies.
- Evaluates stock shortages between Sales Orders and MRP records, creating deduplicated alerts in `bi_monitoring_alerts`.

---

## 3. Technology Stack Summary

| Component | Technology | Rationale |
|---|---|---|
| Frontend | React + TypeScript + Vite + Tailwind CSS | Fast responsive enterprise dashboard |
| Backend API | Python 3.12 + FastAPI + Pydantic v2 | High-performance, schema-validated async service |
| Database | Supabase PostgreSQL | Additive schema extension over existing Task Orch data |
| Offline AI | MockAIProvider | Zero-cost deterministic testing |
| Online AI | OpenRouter Gateway | Synthetic experimentation with free-tier model safety |
