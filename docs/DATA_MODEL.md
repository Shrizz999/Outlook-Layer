# Data Model — Balbird Intelligence

## 1. Baseline Schema (Legacy Protected Tables)

From `Schema.md`, these 16 tables are treated as strictly ADDITIVE. They are preserved intact:

| Table | Primary Key | Key Types & Constraints |
|---|---|---|
| `purchase_orders` | `id` | `uuid` |
| `inventory` | `id` | `int8` identity, `item_code text unique` |
| `part_vendors` | `id` | `int8` |
| `tasks` | `task_id` | `text` (Primary identifier) |
| `monthly_goals` | `goal_id` | `text` |
| `extension_requests` | `request_id` | `uuid` |
| `company_sops` | `id` | `uuid` |
| `boss_reviews` | `review_id` | `uuid` |
| `employees` | `id` | `uuid`, `name text unique` |
| `task_history` | `id` | `uuid`, `task_id text` |
| `workflows` | `id` | `uuid`, `workflow_id text unique` |
| `task_dependencies` | `id` | `uuid`, `predecessor_task_id text`, `successor_task_id text` |
| `workflow_participants` | `id` | `uuid` |
| `task_nudges` | `id` | `uuid` |
| `task_handover_events` | `id` | `uuid` |
| `task_delay_events` | `id` | `uuid` |

---

## 2. Balbird Intelligence Extension Entities (`bi_*`)

### Master Data
- `bi_departments`: Department reference (`id`, `code`, `name`, `parent_id`, `is_active`).
- `bi_user_profiles`: Links `employees.id` (UUID) with `bi_role` and `department_id`.
- `bi_customers`: Customer directory with aliases JSONB for fuzzy lookup.
- `bi_suppliers`: Supplier directory with aliases JSONB.
- `bi_parts`: Canonical part catalog linked via soft-ref to `inventory.item_code`.

### Business Cases
- `bi_business_cases`: Central coordination entity (`id`, `case_number`, `title`, `case_type`, `status`, `priority`, `primary_customer_id`, `primary_owner_employee_id`).
- `bi_case_parties`: Roles of participants (Customer, Supplier, Internal).
- `bi_case_links`: Polymorphic link table connecting cases to messages, orders, RFQs, and tasks with match method and confidence.

### Communication & Intelligence
- `bi_source_mailboxes`: Mailbox connection configurations.
- `bi_conversations`: Thread identifiers.
- `bi_source_messages`: Preprocessed emails with SHA-256 body hash and quoted history separation.
- `bi_email_analyses`: Versioned structured AI analysis results.
- `bi_extracted_facts`: Fact assertions with exact source evidence excerpts.
- `bi_commitments`: Promised delivery dates and quantities from suppliers/customers.

### Orders & MRP
- `bi_sales_orders` & `bi_sales_order_lines`: Imported sales order demand.
- `bi_rfqs` & `bi_rfq_lines`: Large RFQ line storage.
- `bi_purchase_order_ext`: Non-destructive extension to legacy `purchase_orders`.
- `bi_mrp_snapshots` & `bi_mrp_records`: Material stock snapshots and computed shortages.

### Task Coordination & Risk
- `bi_task_proposals`: Staging table for AI-generated actions before human approval.
- `bi_task_metadata`: Extension table referencing legacy `tasks.task_id` (`TEXT`).
- `bi_task_sources`: Traceability link from legacy tasks to source email messages.
- `bi_dependencies`: Directed dependency graph with blocker flags.
- `bi_monitoring_alerts`: Deduplicated risk alerts with suggested actions.
- `bi_smart_drafts`: Human-reviewed response drafts.
