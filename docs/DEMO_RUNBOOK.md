# End-to-End Demonstration Runbook — Balbird Intelligence

This runbook guides reviewers through the mandatory 22-step synthetic demonstration scenario defined in the Master Specification.

## Scenario: Acme Engineering Order for Part HT-2045 (SO-1025)

### Step 1: Launch Backend
In a terminal, navigate to the `backend/` directory and run:
```bash
$env:PYTHONPATH = "."
uvicorn app.main:app --reload --port 8000
```
Verify the server is running by opening:
[http://localhost:8000/health](http://localhost:8000/health)

### Step 2: Seed Synthetic Demo Data
Run the repeatable seeder:
```bash
python scripts/seed_demo_data.py
```
This populates:
- 6 departments (`SALES`, `PURCHASE`, `PPC`, `PRODUCTION`, `QUALITY`, `DISPATCH`)
- 8 employees in the legacy `employees` table
- 3 customers, 3 suppliers, 12 parts
- Sales Order `SO-1025` (100 MTR of `HT-2045` and 50 EA of `FL-1002`)
- MRP Snapshot showing 60 MTR of `HT-2045` in stock (identifying a 40-unit shortage)
- 3 synthetic emails, preprocessed and analyzed with `MockAIProvider`
- Business Case `CASE-2026-00001` linked to `SO-1025`
- Operational tasks in the legacy `tasks` table with `task_id` (`TASK-00100`, etc.)
- Task dependencies and a material shortage alert

### Step 3: Launch Frontend
In a separate terminal, navigate to `frontend/` and run:
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173).

---

## Interactive Verification Walkthrough

1. **Executive Overview Dashboard (`/`):**
   - Confirm stat cards display: Open Business Cases (1), Active Tasks (3), Overdue (0), Blocked Work (1), Active Risk Alerts (1).
   - Check the **Active Operational Risks & Shortages** card: displays `MATERIAL_SHORTAGE: Material shortage of 40 units detected for part HT-2045 on SO-1025`.
   - Inspect the **Department Workload** breakdown.
2. **Email Intelligence (`/inbox`):**
   - Click on `MSG-001` (Acme Tube Enquiry).
   - Verify authored body is separated from signatures and quoted history.
   - Inspect the **AI Intelligence Findings** badge showing Department (`SALES`), Intent (`ENQUIRY`), and extracted reference `SO-1025`.
3. **Business Cases (`/cases`):**
   - Inspect `CASE-2026-00001` (`Acme Hydraulic Tube Order (SO-1025)`).
   - Verify linked objects include Sales Order `SO-1025` and Customer `Acme Engineering Ltd`.
4. **Tasks & Proposals (`/tasks`):**
   - View **AI Proposals**: Review candidate tasks proposed by the AI engine.
   - Click **Approve & Assign**: Observe the proposal transition to `APPROVED` and an operational task record created with formatted `task_id` in the legacy `tasks` table.
   - Switch to **Operational Tasks**: Confirm the task is visible with Assignee, Department, Deadline, and Priority.
5. **Dependency Graph (`/dependencies`):**
   - View the active blocking relationship: `TASK-00101` (Supplier Delivery) -> blocks -> `TASK-00102` (PPC Production Cutting).
   - Attempt to add an invalid cycle: the backend cycle detection rejects circular relationships.
6. **SO & MRP Reference (`/orders`):**
   - Select `SO-1025`.
   - Line 1 (`HT-2045`): Shows **Shortage (60/100)** badge.
   - Line 2 (`FL-1002`): Shows **Available (150 in stock)** badge.
7. **Smart Drafts (`/drafts`):**
   - Select `Supplier Delivery Follow-up`.
   - Observe auto-filled context (Part `HT-2045`, Quantity `40 MTR`, Supplier `Apex Tube Mills`).
   - Click **Copy to Outlook** with clipboard confirmation. Note the zero-hallucination warning banner.
8. **AI & Diagnostics (`/diagnostics`):**
   - Confirm provider is `MockAIProvider` (deterministic, zero external cost).
   - Confirm Daily Budget (40 req/day) and Additive Database protection status.
