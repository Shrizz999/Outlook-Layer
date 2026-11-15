-- =============================================================================
-- Migration V006: Department HOD Management and Task Handoffs
-- Created: 2026-11-07
-- Purpose: Additive tables for HOD assignment audit history, formal department
--          handoffs, and physical operational verification records.
-- Existing tables affected: NONE (16 legacy tables untouched)
-- Rollback: See rollback/R006__rollback.sql
-- =============================================================================

-- Department HOD History (Audit-preserved HOD assignments)
CREATE TABLE IF NOT EXISTS bi_department_hods (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id   UUID NOT NULL REFERENCES bi_departments(id) ON DELETE CASCADE,
    employee_id     UUID NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_by     TEXT NOT NULL DEFAULT 'SYSTEM_ADMIN',
    revoked_at      TIMESTAMPTZ,
    revocation_reason TEXT,
    notes           TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Partial unique index: only ONE active HOD per department at any time
CREATE UNIQUE INDEX IF NOT EXISTS idx_bi_dept_active_hod 
ON bi_department_hods(department_id) 
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_bi_dept_hod_emp ON bi_department_hods(employee_id);

-- Formal Inter-Department Task Handoffs
CREATE TABLE IF NOT EXISTS bi_task_handovers (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id                 TEXT NOT NULL,
    business_case_id        UUID REFERENCES bi_business_cases(id) ON DELETE SET NULL,
    from_department_id      UUID REFERENCES bi_departments(id),
    to_department_id        UUID REFERENCES bi_departments(id),
    from_employee_id        UUID REFERENCES employees(id),
    to_employee_id          UUID REFERENCES employees(id),
    status                  TEXT NOT NULL DEFAULT 'PENDING_ACCEPTANCE', -- PENDING_ACCEPTANCE, ACCEPTED, REJECTED
    checklist               JSONB NOT NULL DEFAULT '[]',
    handover_notes          TEXT,
    rejection_reason        TEXT,
    initiated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    responded_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_task_handovers_status_check CHECK (
        status IN ('PENDING_ACCEPTANCE', 'ACCEPTED', 'REJECTED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_task_handovers_task ON bi_task_handovers(task_id);
CREATE INDEX IF NOT EXISTS idx_bi_task_handovers_status ON bi_task_handovers(status);

-- Physical Operational Verification Records (e.g., Dispatch Challans, Goods Receipts)
CREATE TABLE IF NOT EXISTS bi_physical_verifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_type   TEXT NOT NULL, -- DISPATCH_CHALLAN, GOODS_RECEIPT, QUALITY_INSPECTION_REPORT, GATE_PASS
    document_reference  TEXT NOT NULL, -- e.g. DC-2026-9021
    document_date       DATE,
    related_so_number   TEXT,
    related_po_number   TEXT,
    part_number         TEXT,
    verified_quantity   NUMERIC,
    unit_of_measure     TEXT DEFAULT 'EA',
    source_filename     TEXT,
    verified_by_user_id TEXT,
    notes               TEXT,
    is_verified         BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_physical_verifications_doc ON bi_physical_verifications(document_reference);
CREATE INDEX IF NOT EXISTS idx_bi_physical_verifications_so ON bi_physical_verifications(related_so_number);
