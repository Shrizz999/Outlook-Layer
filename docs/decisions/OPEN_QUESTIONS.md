# Open Questions — Balbird Intelligence
**Maintained by:** AI coding agent  
**Last updated:** 2026-11-06

All decisions below are UNRESOLVED and block specific implementation choices.
Local fabricated-data development proceeds without them. Production deployment requires all to be resolved.

---

## Q001 — Supabase Project Credentials
**Status:** UNRESOLVED  
**Blocking:** Backend database connection, migration execution, RLS testing  
**Required:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`  
**Action:** Provide credentials via `.env` file (never committed to source control)

## Q002 — OpenRouter API Key
**Status:** UNRESOLVED  
**Blocking:** Live AI analysis (MockAIProvider used until resolved)  
**Required:** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`  
**Note:** POC default is MockAIProvider. Real key requires synthetic data only.

## Q003 — n8n Workflow Inventory
**Status:** UNRESOLVED  
**Blocking:** n8n integration design  
**Required:** Access to existing n8n instance to audit workflows before creating new triggers  
**Action:** Provide n8n URL and credentials for read-only audit

## Q004 — Approved Mailbox for Pilot
**Status:** UNRESOLVED  
**Blocking:** Microsoft Graph integration (not required for POC with synthetic data)  
**Required:** Customer IT approval, specific mailbox, permission scope

## Q005 — SO/MRP Workbook Structure
**Status:** UNRESOLVED  
**Blocking:** Column mapping configuration for real imports  
**Note:** Synthetic column mapping defined in code; real workbook structure needed for production mapping

## Q006 — Department Taxonomy
**Status:** PARTIALLY RESOLVED  
**Working assumption (POC):** Sales, Purchase, Engineering, PPC, Production, Quality, Dispatch, Logistics, Finance  
**Required:** Customer confirmation of exact department names and codes

## Q007 — Employee Assignment Rules
**Status:** UNRESOLVED  
**Blocking:** Task owner suggestion logic  
**Required:** Rules for how tasks get suggested to specific employees vs. department queues

## Q008 — Business Timezone
**Status:** UNRESOLVED (defaulting to UTC in development)  
**Required:** Timezone for deadline calculation and display

## Q009 — Task Status Vocabulary
**Status:** PARTIALLY RESOLVED  
**Existing `tasks` table uses:** free-text status field (no enum constraint)  
**BI assumption:** Will use controlled values in `bi_task_proposals`. Approved tasks use existing tasks.status field.  
**Required:** Confirm approved status vocabulary with product owner

## Q010 — Identifier Format Conventions
**Status:** UNRESOLVED  
**Required:** Actual SO, PO, RFQ, part number formats used in customer system (for regex validation)

## Q011 — Email Retention Policy
**Status:** UNRESOLVED  
**Working assumption:** Body text stored during POC under synthetic-data-only policy. Policy for real data TBD.

## Q012 — Smart Draft Templates
**Status:** UNRESOLVED  
**Working assumption:** Generic templates used. Approved company wording required for production.

## Q013 — Historical Data Scope
**Status:** DEFERRED  
**Decision:** No historical data import in Phase 0-5. Design supports incremental backfill.

## Q014 — Multi-Tenant Requirement
**Status:** UNRESOLVED  
**Working assumption:** Single-tenant POC. Multi-tenant isolation design deferred.

## Q015 — Performance SLA
**Status:** UNRESOLVED  
**Working target (POC):** Sub-2s dashboard loads, sub-5s email import, async AI processing

---

## Decision Log (resolved items)

| ID | Decision | Date | Owner |
|----|----------|------|-------|
| D001 | Greenfield implementation — no existing frontend/backend to preserve | 2026-11-06 | Audit |
| D002 | All new tables use `bi_` prefix to protect existing schema | 2026-11-06 | Architect |
| D003 | `tasks.task_id` is TEXT — all BI references use TEXT, not UUID | 2026-11-06 | Architect |
| D004 | MockAIProvider is default; OpenRouter requires explicit config | 2026-11-06 | Architect |
| D005 | Existing RLS policies documented as findings, not modified | 2026-11-06 | Architect |
