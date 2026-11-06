# Master Implementation Plan — Balbird Intelligence POC

**Document Version:** 1.0  
**Target Architecture:** FastAPI + React/TS + Supabase PostgreSQL (Additive) + OpenRouter/Mock AI  
**Deployment Target:** Local Development / Customer Azure-ready  

---

## Phase Overview & Progress

```
Phase 0 [Audit & Protection] (Complete)
   │
   ▼
Phase 1 [Foundation & Database Extensions] (In Progress)
   │
   ▼
Phase 2 [Email Ingestion & Preprocessing]
   │
   ▼
Phase 3 [AI Intelligence Engine]
   │
   ▼
Phase 4 [Business Context & Case Matching]
   │
   ▼
Phase 5 [Task Integration & Task Orch Mapping]
   │
   ▼
Phase 6 [SO/MRP Workbook Importer & Reconciliation]
   │
   ▼
Phase 7 [Dependency Engine & Risk Monitoring]
   │
   ▼
Phase 8 [Smart Drafts & Multi-Role Dashboards]
   │
   ▼
Phase 9 [Verification, Regression & E2E Demo]
```

---

## Detailed Phase Breakdown

### Phase 0: Repository & Schema Audit (DONE)
- [x] Inspect existing repo structure (greenfield codebase confirmed).
- [x] Verify baseline schema from `Schema.md` (16 legacy tables).
- [x] Document RLS policy observations (public access findings).
- [x] Create ADRs, compatibility mappings, open questions, and progress context.

### Phase 1: Foundation & Master Data (Current)
1. **Migrations V001 to V005:**
   - Create tables `bi_departments`, `bi_user_profiles`, `bi_customers`, `bi_suppliers`, `bi_parts`.
   - Create tables `bi_business_cases`, `bi_case_parties`, `bi_case_links`.
   - Create email tables (`bi_source_mailboxes`, `bi_source_messages`, `bi_conversations`, `bi_email_analyses`).
   - Create order & MRP tables (`bi_sales_orders`, `bi_sales_order_lines`, `bi_rfqs`, `bi_mrp_records`).
   - Create task intelligence tables (`bi_task_proposals`, `bi_task_metadata`, `bi_dependencies`, `bi_smart_drafts`, `bi_monitoring_alerts`).
2. **Backend Repository Layer:**
   - Database client with Supabase connectivity + in-memory mock repository for hermetic unit testing.
   - Master data CRUD services (Departments, Employees, Customers, Suppliers, Parts).
3. **Synthetic Seed Script:**
   - `scripts/seed_demo_data.py`: Populate 4 departments, 8 employees, 3 customers, 3 suppliers, 12 parts.
4. **Frontend Scaffolding:**
   - Vite React TypeScript Tailwind app with layout, navigation, role selector, and theme.

### Phase 2: Email Ingestion & Preprocessing
1. **Fixture Importer:**
   - Ingestion service supporting single `.eml`, `.json`, and bulk batch files.
   - Deduplication by `(source_mailbox_id, provider_message_id)` or SHA-256 body hash.
2. **Preprocessing Service:**
   - Normalize line endings and text encodings.
   - Quoted history regex/heuristic detection (separate newest reply from previous thread).
   - Email signature and disclaimer identification.
3. **Conversation Linking:**
   - Thread grouping via `provider_conversation_id` or sanitized subject headers.
4. **Job Queue:**
   - Background worker task dispatching for asynchronous processing.

### Phase 3: AI Intelligence Engine
1. **Adapter Implementations:**
   - `MockAIProvider`: Zero-network deterministic responses for standard synthetic patterns.
   - `OpenRouterAIProvider`: OpenAI-compatible client with quota gating, rate limits, and structured JSON output.
2. **Schema Validation:**
   - Strict Pydantic models for domain, intent, priority, entities, references, dates, actions, and commitments.
3. **Evidence Extraction:**
   - Ensure every extracted reference, date, and action retains an exact text excerpt span.
4. **Review Queue Dispatcher:**
   - Flags low-confidence or ambiguous extractions into `bi_review_queue`.

### Phase 4: Business Context Engine
1. **Deterministic Identifier Matcher:**
   - Regex and exact lookups for SO-*, PO-*, RFQ-*, and Part Numbers.
2. **Candidate Case Scorer:**
   - Weight signals: exact identifier (+50), active thread (+30), customer/supplier match (+20), subject similarity (+5).
3. **Case Associator:**
   - Auto-link if score >= 80 and no conflicts; otherwise send to human review queue.
   - Support multi-case linking when one email affects multiple orders.

### Phase 5: Task Integration & Task Orch Compatibility
1. **Task Proposal Workflow:**
   - Convert validated AI actions into `bi_task_proposals`.
2. **Task Orch Bridge:**
   - On human approval, insert operational task into existing `tasks` table (`task_id` formatted as `TASK-XXXXX` TEXT).
   - Write extension records to `bi_task_metadata`, `bi_task_sources`, and `bi_task_assignment_history`.
3. **Task Deduplication:**
   - Prevent identical open tasks for the same case/action.

### Phase 6: SO & MRP Importers
1. **Workbook Parser:**
   - OpenPyXL / Pandas loader supporting `.xlsx` and `.csv`.
2. **Schema Mapping & Preview:**
   - Column mapping interface with validation of numbers, dates, and mandatory IDs.
3. **Reconciliation Engine:**
   - Cross-check SO line quantities against MRP stock records; compute potential shortages and link risks to Business Cases.

### Phase 7: Dependencies & Monitoring
1. **Dependency Engine:**
   - Represent predecessor/successor tasks, material delivery dependencies, and PPC scheduling.
   - Depth-first search (DFS) cycle detection to reject circular relationships.
2. **Monitoring & Risk Rules:**
   - Periodic/event-driven sweeps for overdue tasks, unassigned proposals, blocked tasks, and material shortages.
   - Generate deduplicated alerts in `bi_monitoring_alerts`.

### Phase 8: Smart Drafts & Dashboards
1. **Smart Draft Generator:**
   - Template-based and AI-assisted drafts (e.g., supplier delivery follow-ups) with clear placeholders for unverified values.
   - Approval-only workflow (sending disabled).
2. **Multi-Role Dashboards:**
   - Employee View, Team Leader View, Department Head View, Management Overview.
   - Server-side filtering by Customer, Supplier, SO, Status, and Priority.

### Phase 9: Evaluation & Demonstration
1. **Automated Test Suite:**
   - Unit tests, API integration tests, and scenario verification.
2. **End-to-End Synthetic Runbook:**
   - Demonstrate the complete 22-step synthetic customer order lifecycle (SO-1025 / Part HT-2045).
