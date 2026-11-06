# Architecture Decision Records (ADRs) — Balbird Intelligence

## ADR-001: Greenfield Extension of Existing Supabase Database
- **Status:** Accepted
- **Context:** The repository is greenfield (contains no prior frontend or backend code), but connects to an existing Supabase instance powering Task Orch with 16 populated tables (`tasks`, `employees`, `workflows`, etc.).
- **Decision:** Build Balbird Intelligence as a modular backend (FastAPI) and modern frontend (React/TypeScript) that treats the existing database as strictly ADDITIVE. All new tables must use the `bi_` prefix to guarantee zero collision with current and future Task Orch tables.
- **Consequences:** Existing tables, columns, indexes, and RLS policies are preserved without modification. Compatibility layers and extension tables (e.g. `bi_task_metadata`) link to existing records using their exact native data types (`tasks.task_id` as `TEXT`, `employees.id` as `UUID`).

---

## ADR-002: AI Provider Abstraction with Deterministic Mock Default
- **Status:** Accepted
- **Context:** Real customer emails cannot be sent to third-party LLMs without strict authorization. Developers, CI pipelines, and unit tests must run reliably without network access, credentials, or rate limits.
- **Decision:** Implement the `AIProvider` Protocol with `MockAIProvider` as the default. OpenRouter is configurable via `OpenRouterAIProvider` with conservative token/request rate-limiting and budget controls for synthetic datasets only.
- **Consequences:** Tests run offline at zero cost. Quota exhaustion triggers a retryable `WAITING_FOR_PROVIDER_QUOTA` state instead of application crashes or synthetic data corruption.

---

## ADR-003: Task Proposal Approval Lifecycle
- **Status:** Accepted
- **Context:** Email processing frequently detects requests, clarifications, and action items. However, inserting unverified tasks into operational queues causes duplicate tasks, phantom assignments, and user fatigue.
- **Decision:** Tasks extracted by AI are stored in `bi_task_proposals` in `PENDING` status. Only upon explicit human approval (or approved deterministic rule criteria) is an authoritative record created in the existing `tasks` table (`task_id` TEXT), with rich source provenance saved to `bi_task_sources` and `bi_task_metadata`.
- **Consequences:** The operational Task Orch system is never polluted by speculative AI hallucination. Full lineage to the originating email is maintained.

---

## ADR-004: Two Independent Input Pipelines Converging via Business Context Engine
- **Status:** Accepted
- **Context:** Email communication arrives asynchronously via Outlook (or synthetic fixtures), while operational references arrive in batches via SO registers and MRP spreadsheets.
- **Decision:** Decouple email ingestion from SO/MRP workbook imports. Both pipelines write to their respective staging/canonical tables and converge inside the `BusinessContextEngine`, which uses multi-signal candidate scoring (exact IDs, aliases, thread relationships) to associate emails and orders with unified `bi_business_cases`.
- **Consequences:** Imports and emails can arrive in any order; missing SO data does not block email classification, and cases update dynamically when new matching evidence arrives.

---

## ADR-005: Strict Identifier Type Discipline
- **Status:** Accepted
- **Context:** In `Schema.md`, `tasks.task_id` is defined as `TEXT`, while `employees.id` and `workflows.id` are `UUID`. In `task_dependencies`, task references are `TEXT`.
- **Decision:** Foreign keys to `tasks` must explicitly use `TEXT`. Foreign keys to `employees` or `workflows` must use `UUID`. The application layer will enforce validation and never assume uniform UUID keys across legacy and new tables.
- **Consequences:** Prevents runtime PostgreSQL foreign key type mismatch errors (`operator does not exist: text = uuid`).
