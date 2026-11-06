# Security, Privacy & Data Flow — Balbird Intelligence

## 1. Data Flow Transparency

```
[Synthetic Fixtures / Pilot Mailbox]
                │
                ▼ (Metadata & Body Read)
      [Email Ingestion Service]
                │
                ▼ (Cleaned body, stripped quotes, SHA-256 hash)
         [FastAPI Backend]
                │
                ├────────────────────────────────────────┐
                ▼ (Synthetic Data Only)                  ▼ (Encrypted in transit)
        [MockAIProvider / OpenRouter]           [Supabase PostgreSQL]
                │                                (Additive bi_* tables)
                ▼ (Structured JSON validation)           │
       [Domain Services & Rules]                         │
                │                                        ▼
                └───────────────────────────────► [React Dashboard]
                                                (Role-based UI + Token Auth)
```

---

## 2. Security Controls & Guardrails

1. **Synthetic Data Policy:**
   - Initial development and testing use fabricated data exclusively.
   - Real customer/STAUFF emails, drawings, and customer names are prohibited without written authorization.
2. **Zero API Key Leakage:**
   - AI provider secrets (`OPENROUTER_API_KEY`) and database service role keys (`SUPABASE_SERVICE_ROLE_KEY`) are kept on the backend.
   - Diagnostics endpoints (`/api/v1/admin/ai-usage`) display quota counters and provider names, never keys.
3. **Additive Database Constraint:**
   - No `DROP TABLE`, `DROP COLUMN`, or `RENAME` commands are ever run against the Supabase database.
   - All new entities use the `bi_` prefix.
4. **No Autonomous Destructive Actions:**
   - Automatic email sending is strictly disabled. Smart Drafts require human review and copy-to-clipboard.
   - ERP/MRP source spreadsheets are immutable reference snapshots; the system never mutates source workbooks.
   - Tasks extracted from emails are created in `bi_task_proposals` in `PENDING` status. Only authorized human approval promotes them to operational tasks in the legacy `tasks` table.
5. **Prompt Injection Defense:**
   - Email content is processed strictly as data in separate JSON payload fields, never concatenated directly into system instruction headers.
   - Strict Pydantic schemas enforce typed field validation on all AI outputs.
