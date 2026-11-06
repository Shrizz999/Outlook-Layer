# Schema Compatibility Map — Balbird Intelligence
**Generated:** 2026-11-06  
**Baseline:** Schema.md  
**Policy:** ADDITIVE ONLY — no existing tables modified

---

## Decision Key

| Symbol | Meaning |
|--------|---------|
| ✅ REUSE | Use existing table as-is |
| ➕ EXTEND | Reuse + add extension table referencing it |
| 🆕 NEW | New table required (no equivalent exists) |
| 🔒 APPROVAL | Requires explicit approval before any modification |

---

## Existing Tables — Reuse and Extension Map

### `employees` (UUID pk)
- **Existing purpose:** Employee master — name, department, email, employee_number
- **BI reuse:** Use as the canonical employee reference. Map to Balbird users via `bi_user_profiles` extension.
- **Extension needed:** `bi_user_profiles` — adds role, is_active, department FK to new `bi_departments`, last_login
- **Migration required:** No modification to `employees`. New extension table only.
- **Classification:** ✅ REUSE + ➕ EXTEND

### `tasks` (TEXT pk: `task_id`)
- **Existing purpose:** Operational task records with status, assignment, deadline, checklist, workflow association
- **BI reuse:** AI-proposed tasks, once approved, will create records in this table. This is the authoritative task store.
- **Extension needed:** `bi_task_metadata` — links `tasks.task_id` (TEXT) to business_case, source_message, extraction confidence, proposal status, verification state
- **Important:** `task_id` is TEXT. All BI references to tasks MUST use TEXT, not UUID.
- **Classification:** ✅ REUSE + ➕ EXTEND

### `task_dependencies` (UUID pk; `workflow_id` UUID FK to `workflows.id`)
- **Existing purpose:** Predecessor/successor task dependency relationships within workflows
- **BI reuse:** Existing task_dependencies can represent BI task dependencies when tasks are within a workflow context. For cross-workflow and business-object dependencies, use new `bi_dependencies` table.
- **Extension needed:** `bi_dependencies` — supports richer dependency types, source evidence, confidence, validation, and cross-workflow relationships
- **Classification:** ✅ REUSE + 🆕 NEW (bi_dependencies)

### `task_history` (UUID pk)
- **Existing purpose:** Full JSONB before/after snapshots of task changes
- **BI reuse:** No change. BI task updates that modify tasks table records will naturally produce task_history records via existing triggers/application logic.
- **Extension needed:** `bi_task_updates` — BI-specific update records with AI evidence, reasons, source links
- **Classification:** ✅ REUSE

### `workflows` (UUID pk; TEXT `workflow_id` unique)
- **Existing purpose:** Workflow templates with status, participants, dates
- **BI reuse:** Reference existing workflows for task-workflow association. BI may propose new workflow-linked tasks.
- **Extension needed:** `bi_business_case_workflows` — optional link between Business Cases and Workflows
- **Classification:** ✅ REUSE

### `purchase_orders` (UUID pk)
- **Existing purpose:** PO headers with company name, file path, order date
- **BI reuse:** Reference existing PO records. BI will NOT replace this table.
- **Extension needed:** `bi_purchase_order_ext` — adds supplier_id FK, source_import_id, expected delivery, status, PO lines
- **Note:** Existing table lacks supplier FK, status, and line items. Extension table handles these without touching existing structure.
- **Classification:** ✅ REUSE + ➕ EXTEND

### `inventory` (int8 identity pk; `item_code` text unique)
- **Existing purpose:** Current stock quantities by item code
- **BI reuse:** Reference for MRP/stock matching. `item_code` will be used to link to BI `bi_parts`.
- **Extension needed:** None — reference via item_code
- **Classification:** ✅ REUSE

### `part_vendors` (int8 pk)
- **Existing purpose:** Part-to-vendor relationships
- **BI reuse:** Reference for supplier-part matching
- **Extension needed:** None — reference via part_code and vendor_name
- **Classification:** ✅ REUSE

---

## New Tables Required (Balbird Intelligence Extension)

All new tables use `bi_` prefix to avoid collision with existing tables.

### Master Data

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_departments` | Department master with codes, hierarchy | — |
| `bi_user_profiles` | BI role/permissions per employee | `employees.id` |
| `bi_customers` | Customer master with aliases | — |
| `bi_suppliers` | Supplier master with aliases | — |
| `bi_parts` | Part master with aliases | `inventory.item_code` (soft ref) |

### Business Cases

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_business_cases` | Central Business Case entity | `employees.id` (owner) |
| `bi_case_parties` | Customers/suppliers per case | `bi_business_cases.id`, `bi_customers.id`, `bi_suppliers.id` |
| `bi_case_links` | Links cases to SO, PO, RFQ, task | `bi_business_cases.id` |

### Email / Communication

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_source_mailboxes` | Mailbox registry | — |
| `bi_source_messages` | Imported email messages | `bi_source_mailboxes.id` |
| `bi_source_attachments` | Attachment metadata | `bi_source_messages.id` |
| `bi_conversations` | Thread/conversation grouping | `bi_source_messages.id` |

### AI Intelligence

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_email_analyses` | AI analysis results per message | `bi_source_messages.id` |
| `bi_extracted_facts` | Individual extracted facts with evidence | `bi_source_messages.id`, `bi_business_cases.id` |
| `bi_commitments` | Supplier/customer commitments | `bi_business_cases.id`, `bi_source_messages.id` |

### Orders / MRP

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_sales_orders` | SO header records | `bi_customers.id` |
| `bi_sales_order_lines` | SO line items | `bi_sales_orders.id`, `bi_parts.id` |
| `bi_rfqs` | RFQ headers | `bi_customers.id` |
| `bi_rfq_lines` | RFQ line items | `bi_rfqs.id`, `bi_parts.id` |
| `bi_purchase_order_ext` | Extended PO data | `purchase_orders.id` (existing) |
| `bi_purchase_order_lines` | PO line items | `bi_purchase_order_ext.id`, `bi_parts.id` |
| `bi_mrp_snapshots` | MRP import snapshots | `bi_imports.id` |
| `bi_mrp_records` | MRP data per part per snapshot | `bi_mrp_snapshots.id`, `bi_parts.id` |
| `bi_imports` | Import batch records | — |

### Task Intelligence

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_task_proposals` | AI-proposed tasks awaiting approval | `bi_source_messages.id`, `bi_business_cases.id` |
| `bi_task_metadata` | BI extension data for approved tasks | `tasks.task_id` (TEXT) |
| `bi_task_sources` | Source evidence per task | `tasks.task_id` (TEXT), `bi_source_messages.id` |
| `bi_task_assignments_hist` | Assignment history | `tasks.task_id` (TEXT), `employees.id` |
| `bi_task_updates` | BI-layer update records | `tasks.task_id` (TEXT) |

### Dependencies

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_dependencies` | Rich dependency graph (cross-workflow capable) | `tasks.task_id` (TEXT) or `bi_business_cases.id` |

### Monitoring

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_monitoring_alerts` | Deduplicating alert records | `bi_business_cases.id`, `tasks.task_id` |

### Smart Drafts

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_smart_drafts` | Generated email draft proposals | `bi_business_cases.id`, `bi_source_messages.id`, `employees.id` |

### Infrastructure

| Table | Purpose | References Existing |
|-------|---------|-------------------|
| `bi_processing_jobs` | Background job queue and state | `bi_source_messages.id` |
| `bi_audit_events` | Audit log for consequential actions | — |
| `bi_human_feedback` | Human corrections to AI outputs | `employees.id` |
| `bi_review_queue` | Items requiring human review | — |
| `bi_ai_usage` | AI provider quota tracking | — |

---

## Identifier Type Mapping

> [!CAUTION]
> This is critical. Mixing identifier types will cause foreign key failures.

| Existing Table | PK Field | PK Type | BI Reference Pattern |
|---------------|----------|---------|---------------------|
| `employees` | `id` | UUID | `employees_id UUID` FK |
| `tasks` | `task_id` | TEXT | `task_id TEXT` (not UUID FK) |
| `workflows` | `id` | UUID | `workflow_uuid UUID` FK |
| `workflows` | `workflow_id` | TEXT unique | `workflow_text_id TEXT` (soft ref) |
| `task_dependencies` | `workflow_id` | UUID (FK to workflows.id) | Use workflows.id UUID |
| `purchase_orders` | `id` | UUID | `purchase_order_id UUID` FK |
| `inventory` | `id` | int8 | `inventory_id BIGINT` or soft ref via `item_code` |
| `part_vendors` | `id` | int8 | `part_vendor_id BIGINT` or soft ref |

---

## Changes Requiring Approval

> [!WARNING]
> The following are **explicitly NOT being done** without approval:

1. Adding columns to `tasks` — using `bi_task_metadata` extension instead
2. Adding columns to `employees` — using `bi_user_profiles` extension instead
3. Adding columns to `purchase_orders` — using `bi_purchase_order_ext` instead
4. Modifying any existing RLS policies
5. Renaming or restructuring any existing table

---

## Migration Strategy

- Each new table delivered as a separate numbered SQL migration file
- Naming: `migrations/V001__bi_departments.sql`, `V002__bi_user_profiles.sql`, etc.
- Every migration is idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
- Rollback strategy: each migration has a corresponding `rollback/R001__rollback.sql`
- No `supabase db reset` will be used — manual `psql` or Supabase dashboard SQL execution only
