# Balbird Intelligence

> An email-centric business intelligence, task coordination, and operational risk-monitoring layer integrating Microsoft Outlook correspondence, Sales Orders (SO), Material Requirements Planning (MRP) reference data, and existing Task Orchestration infrastructure.

---

## Key Features

- **Strict Additive Database Architecture:** Integrates seamlessly into the existing Supabase database without modifying, dropping, or renaming any of the 16 legacy tables (`tasks`, `employees`, `workflows`, etc.).
- **Safe AI Intelligence Engine:** Powered by an abstract `AIProvider` protocol. Defaults to `MockAIProvider` for 100% deterministic, zero-cost offline development and testing; optionally supports `OpenRouterAIProvider` with strict daily request budget gating.
- **Two Independent Converging Pipelines:** Ingests emails (with quoted-history separation and SHA-256 deduplication) and SO/MRP spreadsheets, converging at the **Business Context Engine** to associate activity with unified `bi_business_cases`.
- **Task Orch Bridge:** AI-extracted action items are held in `bi_task_proposals` until approved by a human, upon which authoritative records are created in the legacy `tasks` table (`task_id` formatted as `TEXT`).
- **Dependency & Blocker Graph:** Graph representation with built-in Depth-First Search (DFS) cycle detection that rejects circular dependencies.
- **Real-Time Material Shortage & Overdue Monitoring:** Compares Sales Order demand against MRP available inventory, calculating shortages and generating deduplicated risk alerts.
- **Smart Response Drafts:** Generates context-aware email responses with missing-value warnings and one-click copy-to-clipboard (automated external sending is strictly disabled).
- **Responsive Multi-Role Dashboard:** Custom filtered perspectives for Employees, Team Leaders, Department Heads, and Management.

---

## Quickstart & Verification

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 2. Backend Setup & Tests
```powershell
# Navigate to backend
cd backend

# Configure environment
Copy-Item .env.example .env

# Run automated tests (17 passing unit & integration tests)
$env:PYTHONPATH = "."
pytest tests -v

# Seed synthetic demo dataset
python scripts/seed_demo_data.py

# Launch FastAPI server
uvicorn app.main:app --reload --port 8000
```
API Documentation will be live at: [http://localhost:8000/docs](http://localhost:8000/docs)  
Health Check: [http://localhost:8000/health](http://localhost:8000/health)

### 3. Frontend Setup
```powershell
# Navigate to frontend
cd frontend

# Install dependencies (already installed if cloning complete repo)
npm install

# Start Vite dev server
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Architecture & Documentation Index

- [Repository Audit](file:///c:/Programming/EmailSeg/docs/REPOSITORY_AUDIT.md)
- [Schema Compatibility Map](file:///c:/Programming/EmailSeg/docs/SCHEMA_COMPATIBILITY.md)
- [Architecture Decisions (ADRs)](file:///c:/Programming/EmailSeg/docs/ARCHITECTURE_DECISIONS.md)
- [Master Implementation Plan](file:///c:/Programming/EmailSeg/docs/IMPLEMENTATION_PLAN.md)
- [System Architecture](file:///c:/Programming/EmailSeg/docs/ARCHITECTURE.md)
- [Data Model & Entities](file:///c:/Programming/EmailSeg/docs/DATA_MODEL.md)
- [Security & Data Flow](file:///c:/Programming/EmailSeg/docs/SECURITY_AND_DATA_FLOW.md)
- [Demo Runbook](file:///c:/Programming/EmailSeg/docs/DEMO_RUNBOOK.md)
- [Migration Log](file:///c:/Programming/EmailSeg/docs/MIGRATION_LOG.md)
- [Known Limitations](file:///c:/Programming/EmailSeg/docs/KNOWN_LIMITATIONS.md)
- [Open Questions](file:///c:/Programming/EmailSeg/docs/decisions/OPEN_QUESTIONS.md)
