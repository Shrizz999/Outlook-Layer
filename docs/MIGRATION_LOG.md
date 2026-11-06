# Database Migration Log — Balbird Intelligence

All migrations follow the **Additive Only** policy. No existing tables, columns, or RLS policies are altered.

| Version | Migration File | Description | Rollback Script | Verification Query |
|---|---|---|---|---|
| V001 | `V001__bi_master_data.sql` | Master tables: departments, user profiles, customers, suppliers, parts | `R001__rollback.sql` | `SELECT count(*) FROM bi_departments;` |
| V002 | `V002__bi_business_cases.sql` | Business case entity, parties, links, case number sequence generator | `R002__rollback.sql` | `SELECT bi_next_case_number();` |
| V003 | `V003__bi_email_communication.sql` | Mailboxes, conversations, messages, attachments, AI analyses, facts, commitments, review queue, quota tracking | `R003__rollback.sql` | `SELECT count(*) FROM bi_source_messages;` |
| V004 | `V004__bi_orders_mrp.sql` | Sales orders, order lines, RFQs, PO extensions, MRP snapshots and records, import batches | `R004__rollback.sql` | `SELECT count(*) FROM bi_sales_orders;` |
| V005 | `V005__bi_tasks_dependencies.sql` | Task proposals, metadata extension (linked to `tasks.task_id`), task sources, updates, dependencies, drafts, alerts, audit log, feedback | `R005__rollback.sql` | `SELECT count(*) FROM bi_task_proposals;` |

---

## Migration Safety Guidelines
1. Execute migrations using Supabase SQL Editor or a standard migration runner with service role credentials.
2. Under no circumstance should `supabase db reset` be run.
3. Every table includes `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.
4. All foreign key references to `tasks` use `tasks.task_id` (`TEXT`).
5. All foreign key references to `employees` use `employees.id` (`UUID`).
