# Repository Audit — Balbird Intelligence
**Generated:** 2026-11-06  
**Auditor:** Antigravity (AI coding agent)  
**Status:** Phase 0 — Greenfield Discovery

---

## 1. Repository Inventory

The repository at `c:\Programming\EmailSeg` currently contains **exactly three files**:

| File | Size | Purpose |
|------|------|---------|
| `Balbird_Intelligence_POC_Implementation_Specification.md` | 123 KB | Complete product specification (3,586 lines) |
| `Schema.md` | 9 KB | Existing Supabase database schema |
| `Context.md` | 0 bytes | Empty — to be maintained as progress context |

> [!IMPORTANT]
> This is a **greenfield implementation**. There is no existing frontend, backend, test suite, Docker configuration, environment file, or application code. The only existing asset is the Supabase database described in Schema.md.

---

## 2. Existing Database Inventory

The Supabase database (from `Schema.md`) contains **16 existing tables** belonging to a Task Orchestration ("Task Orch") application:

| Table | Primary Key Type | Purpose |
|-------|-----------------|---------|
| `purchase_orders` | UUID | PO headers with company name, file path |
| `inventory` | int8 (identity) | Stock items by item_code |
| `part_vendors` | int8 | Part-to-vendor relationships |
| `tasks` | TEXT (`task_id`) | Operational task records |
| `monthly_goals` | TEXT (`goal_id`) | Monthly/weekly goal tracking |
| `extension_requests` | UUID | Task deadline extension requests |
| `company_sops` | UUID | Standard Operating Procedures by department |
| `boss_reviews` | UUID | Employee performance reviews |
| `employees` | UUID | Employee master (name, department, email, number) |
| `task_history` | UUID | Full JSONB before/after snapshots of task changes |
| `workflows` | UUID (also `workflow_id` TEXT) | Workflow templates/instances |
| `task_dependencies` | UUID | Task predecessor/successor relationships |
| `workflow_participants` | UUID | Employees per workflow stage |
| `task_nudges` | UUID | Nudge messages between employees on tasks |
| `task_handover_events` | UUID | Task handover records |
| `task_delay_events` | UUID | Delay reason records per task |

### Critical Identifier Note
- `tasks.task_id` is **TEXT** (not UUID)
- `task_dependencies.predecessor_task_id` and `successor_task_id` are **TEXT** references to `tasks.task_id`
- `workflows.workflow_id` is **TEXT** (unique), while `workflows.id` is UUID
- `task_dependencies.workflow_id` references `workflows.id` (UUID), not `workflow_id` (TEXT)

---

## 3. Existing n8n Integration Inventory

No n8n workflow files exist in the repository. The n8n integration is external (community self-hosted). No audit of live n8n workflows was possible without network credentials.

**Action required:** When n8n credentials are available, audit existing workflows before creating new n8n integrations.

---

## 4. Existing Functionality That Must Be Preserved

The following Task Orch capabilities must remain fully operational:

- Task creation, update, status management (`tasks` table)
- Task history recording (`task_history` table)
- Workflow management (`workflows`, `workflow_participants`)
- Task dependency management (`task_dependencies`)
- Employee management (`employees`)
- Extension requests (`extension_requests`)
- Delay event tracking (`task_delay_events`)
- Handover events (`task_handover_events`)
- Nudge messaging (`task_nudges`)
- Monthly goal tracking (`monthly_goals`)
- SOP management (`company_sops`)
- PO tracking (`purchase_orders`)
- Inventory management (`inventory`)
- Vendor management (`part_vendors`)
- Performance reviews (`boss_reviews`)

---

## 5. Existing RLS Policies — Security Findings

> [!WARNING]
> **Security Findings (documented, NOT changed per policy):**

All existing RLS policies use the `public` role with permissive access. This means:

| Table | Finding |
|-------|---------|
| `inventory` | Full ALL access (SELECT/INSERT/UPDATE/DELETE) to anonymous public |
| `employees` | Full ALL access to anonymous public |
| `part_vendors` | SELECT/INSERT/UPDATE to anonymous public (no DELETE restriction) |
| `monthly_goals` | SELECT/INSERT/UPDATE to anonymous public |
| `extension_requests` | SELECT/INSERT/UPDATE to anonymous public |
| `tasks` | SELECT/INSERT/UPDATE to anonymous public |
| `purchase_orders` | SELECT + INSERT only to anonymous public (no UPDATE/DELETE) |
| `boss_reviews` | SELECT only to anonymous public |
| `task_history` | SELECT + INSERT to anonymous public |

**These policies are NOT being changed.** Balbird Intelligence new tables will implement properly scoped RLS policies. The existing overly-permissive policies are flagged here for security review in a future production hardening pass.

---

## 6. Technology Stack Decision

Since this is greenfield, the full specification stack is adopted:

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript + Vite + Tailwind CSS |
| Backend | Python + FastAPI + Pydantic |
| Database | Existing Supabase PostgreSQL (additive only) |
| Auth | Supabase Auth |
| AI | OpenRouter (synthetic data only) + MockAIProvider |
| Spreadsheets | pandas + openpyxl |
| Email parsing | Python `email` package + fixture adapter |
| Background jobs | Python async worker (APScheduler or simple queue) |
| Tests | pytest + httpx |
| Dev environment | Docker Compose (optional, local-first) |

---

## 7. Gap Analysis

| Specification Requirement | Status |
|--------------------------|--------|
| Frontend application | ❌ Not started |
| FastAPI backend | ❌ Not started |
| New database tables (BI-specific) | ❌ Not started |
| Email ingestion service | ❌ Not started |
| AI provider adapter | ❌ Not started |
| Business Case engine | ❌ Not started |
| Task integration layer | ❌ Not started — existing tasks table must be reused |
| SO/MRP importer | ❌ Not started |
| Dependency engine | ❌ Not started — existing task_dependencies must be reused |
| Monitoring/alerts | ❌ Not started |
| Smart Drafts | ❌ Not started |
| Dashboards | ❌ Not started |
| Tests | ❌ Not started |
| Documentation | 🔄 In progress |
| Synthetic seed data | ❌ Not started |
