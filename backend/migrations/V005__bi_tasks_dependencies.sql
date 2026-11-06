-- =============================================================================
-- Migration V005: Balbird Intelligence Task Intelligence and Dependencies
-- Created: 2026-11-06
-- Purpose: Task proposals, extensions to existing tasks, assignment history,
--          task sources, updates, dependencies, smart drafts, audit, feedback,
--          monitoring alerts
-- Existing tables affected: NONE
-- References: tasks.task_id (TEXT), employees.id (UUID),
--             bi_business_cases.id, bi_source_messages.id
-- =============================================================================

-- Task proposals (AI-generated task suggestions BEFORE approval)
CREATE TABLE IF NOT EXISTS bi_task_proposals (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_message_id           UUID REFERENCES bi_source_messages(id),
    email_analysis_id           UUID REFERENCES bi_email_analyses(id),
    business_case_id            UUID REFERENCES bi_business_cases(id),
    title                       TEXT NOT NULL,
    description                 TEXT,
    task_type                   TEXT,                   -- TECHNICAL_CLARIFICATION, QUOTATION, PURCHASE, etc.
    suggested_department        TEXT,
    suggested_department_id     UUID REFERENCES bi_departments(id),
    suggested_owner_employee_id UUID REFERENCES employees(id),
    suggested_assigned_by_employee_id UUID REFERENCES employees(id),
    priority                    TEXT NOT NULL DEFAULT 'NORMAL',
    due_date                    DATE,
    due_date_confidence         NUMERIC(5,4),
    due_date_type               TEXT,                   -- REQUESTED, PROMISED, INTERNAL, INFERRED
    action_evidence             TEXT,                   -- Source excerpt that generated this proposal
    confidence                  NUMERIC(5,4),
    proposal_status             TEXT NOT NULL DEFAULT 'PENDING',
    reviewed_by_employee_id     UUID REFERENCES employees(id),
    reviewed_at                 TIMESTAMPTZ,
    review_notes                TEXT,
    -- If approved, points to the created task
    approved_task_id            TEXT,                   -- tasks.task_id (TEXT) — not UUID
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_task_proposals_priority_check CHECK (
        priority IN ('CRITICAL','HIGH','NORMAL','LOW')
    ),
    CONSTRAINT bi_task_proposals_status_check CHECK (
        proposal_status IN ('PENDING','APPROVED','REJECTED','MERGED','SUPERSEDED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_tp_message ON bi_task_proposals(source_message_id) WHERE source_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_tp_case ON bi_task_proposals(business_case_id) WHERE business_case_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_tp_status ON bi_task_proposals(proposal_status);
CREATE INDEX IF NOT EXISTS idx_bi_tp_approved_task ON bi_task_proposals(approved_task_id) WHERE approved_task_id IS NOT NULL;

-- Task metadata extension (enriches existing tasks table without modifying it)
-- task_id is TEXT (matching tasks.task_id)
CREATE TABLE IF NOT EXISTS bi_task_metadata (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id                 TEXT NOT NULL UNIQUE,       -- References tasks.task_id (TEXT)
    business_case_id        UUID REFERENCES bi_business_cases(id),
    task_proposal_id        UUID REFERENCES bi_task_proposals(id),
    task_type               TEXT,
    due_date_confidence     NUMERIC(5,4),
    due_date_type           TEXT,
    due_date_source         TEXT,                       -- Where the deadline came from
    verification_status     TEXT NOT NULL DEFAULT 'UNVERIFIED',
    completion_reported_at  TIMESTAMPTZ,
    completion_evidence     TEXT,
    delay_reason_category   TEXT,                       -- SUPPLIER, MATERIAL, INTERNAL, CUSTOMER, OTHER
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_task_meta_verification_check CHECK (
        verification_status IN ('UNVERIFIED','VERIFIED','DISPUTED','REOPENED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_tm_task_id ON bi_task_metadata(task_id);
CREATE INDEX IF NOT EXISTS idx_bi_tm_case ON bi_task_metadata(business_case_id) WHERE business_case_id IS NOT NULL;

-- Task sources (links tasks to source messages/facts)
-- task_id is TEXT
CREATE TABLE IF NOT EXISTS bi_task_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             TEXT NOT NULL,              -- References tasks.task_id (TEXT)
    source_message_id   UUID REFERENCES bi_source_messages(id),
    extracted_fact_id   UUID REFERENCES bi_extracted_facts(id),
    relationship_type   TEXT NOT NULL DEFAULT 'DERIVED_FROM',  -- DERIVED_FROM, UPDATED_BY, CONFIRMED_BY
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_ts_task ON bi_task_sources(task_id);
CREATE INDEX IF NOT EXISTS idx_bi_ts_message ON bi_task_sources(source_message_id) WHERE source_message_id IS NOT NULL;

-- Task assignment history (extends existing tasks without modifying it)
-- task_id is TEXT
CREATE TABLE IF NOT EXISTS bi_task_assignment_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             TEXT NOT NULL,              -- References tasks.task_id (TEXT)
    employee_id         UUID REFERENCES employees(id),
    employee_name       TEXT,                       -- Denormalised for resilience
    assignment_role     TEXT NOT NULL DEFAULT 'ASSIGNEE',  -- ASSIGNEE, REVIEWER, OBSERVER
    assigned_by_employee_id UUID REFERENCES employees(id),
    assigned_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    reason              TEXT
);

CREATE INDEX IF NOT EXISTS idx_bi_tah_task ON bi_task_assignment_history(task_id);
CREATE INDEX IF NOT EXISTS idx_bi_tah_employee ON bi_task_assignment_history(employee_id) WHERE employee_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_tah_active ON bi_task_assignment_history(task_id, ended_at) WHERE ended_at IS NULL;

-- Task updates (BI-layer progress and status records)
-- task_id is TEXT
CREATE TABLE IF NOT EXISTS bi_task_updates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             TEXT NOT NULL,              -- References tasks.task_id (TEXT)
    updated_by_employee_id UUID REFERENCES employees(id),
    previous_status     TEXT,
    new_status          TEXT,
    update_text         TEXT,
    reason_for_delay    TEXT,
    delay_category      TEXT,
    evidence_reference  TEXT,
    source_message_id   UUID REFERENCES bi_source_messages(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_tu_task ON bi_task_updates(task_id);
CREATE INDEX IF NOT EXISTS idx_bi_tu_created ON bi_task_updates(created_at);

-- Dependencies (richer than existing task_dependencies; supports cross-workflow)
-- predecessor_task_id and successor_task_id reference tasks.task_id (TEXT)
CREATE TABLE IF NOT EXISTS bi_dependencies (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Predecessor
    predecessor_type        TEXT NOT NULL DEFAULT 'TASK',  -- TASK, SO, PO, COMMITMENT, EXTERNAL
    predecessor_task_id     TEXT,                           -- tasks.task_id if TASK
    predecessor_object_id   TEXT,                           -- ID for non-task types
    -- Successor
    successor_type          TEXT NOT NULL DEFAULT 'TASK',
    successor_task_id       TEXT,                           -- tasks.task_id if TASK
    successor_object_id     TEXT,
    -- Relationship
    dependency_type         TEXT NOT NULL DEFAULT 'BLOCKS', -- BLOCKS, DEPENDS_ON, RELATED_TO, WAITING_FOR_EXTERNAL
    status                  TEXT NOT NULL DEFAULT 'ACTIVE',
    is_blocking             BOOLEAN NOT NULL DEFAULT false,
    reason                  TEXT,
    source_message_id       UUID REFERENCES bi_source_messages(id),
    confidence              NUMERIC(5,4),
    validation_status       TEXT NOT NULL DEFAULT 'UNREVIEWED',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_employee_id  UUID REFERENCES employees(id),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_dep_pred_type_check CHECK (
        predecessor_type IN ('TASK','SO','PO','COMMITMENT','EXTERNAL')
    ),
    CONSTRAINT bi_dep_succ_type_check CHECK (
        successor_type IN ('TASK','SO','PO','COMMITMENT','EXTERNAL')
    ),
    CONSTRAINT bi_dep_type_check CHECK (
        dependency_type IN ('BLOCKS','DEPENDS_ON','RELATED_TO','WAITING_FOR_EXTERNAL',
                            'FINISH_TO_START','START_TO_START','FINISH_TO_FINISH',
                            'REQUIRES_APPROVAL','REQUIRES_MATERIAL','REQUIRES_QC')
    ),
    CONSTRAINT bi_dep_status_check CHECK (
        status IN ('ACTIVE','SATISFIED','REMOVED','BYPASSED')
    ),
    -- Prevent exact self-dependencies
    CONSTRAINT bi_dep_no_self_task CHECK (
        NOT (predecessor_type = 'TASK' AND successor_type = 'TASK'
             AND predecessor_task_id = successor_task_id)
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_dep_pred_task ON bi_dependencies(predecessor_task_id) WHERE predecessor_task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_dep_succ_task ON bi_dependencies(successor_task_id) WHERE successor_task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_dep_status ON bi_dependencies(status);
CREATE INDEX IF NOT EXISTS idx_bi_dep_blocking ON bi_dependencies(is_blocking) WHERE is_blocking = true;

-- Smart drafts
CREATE TABLE IF NOT EXISTS bi_smart_drafts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_case_id        UUID REFERENCES bi_business_cases(id),
    source_message_id       UUID REFERENCES bi_source_messages(id),
    created_by_employee_id  UUID NOT NULL REFERENCES employees(id),
    template_key            TEXT NOT NULL,          -- e.g. 'SUPPLIER_FOLLOWUP', 'CUSTOMER_ACK'
    draft_type              TEXT NOT NULL,          -- SUPPLIER_ENQUIRY, CUSTOMER_REPLY, INTERNAL, etc.
    recipient_suggestions   JSONB NOT NULL DEFAULT '[]',
    subject                 TEXT,
    body                    TEXT,
    missing_fields          JSONB NOT NULL DEFAULT '[]',  -- [{field, reason}]
    warnings                JSONB NOT NULL DEFAULT '[]',  -- [{warning_type, message}]
    approval_status         TEXT NOT NULL DEFAULT 'DRAFT',
    approved_by_employee_id UUID REFERENCES employees(id),
    approved_at             TIMESTAMPTZ,
    send_permitted          BOOLEAN NOT NULL DEFAULT false,  -- Disabled in V1
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_drafts_status_check CHECK (
        approval_status IN ('DRAFT','APPROVED','DISCARDED','SENT')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_drafts_case ON bi_smart_drafts(business_case_id) WHERE business_case_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_drafts_created_by ON bi_smart_drafts(created_by_employee_id);

-- Monitoring alerts
CREATE TABLE IF NOT EXISTS bi_monitoring_alerts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type              TEXT NOT NULL,              -- OVERDUE_TASK, NO_OWNER, BLOCKED, SUPPLIER_RISK, etc.
    severity                TEXT NOT NULL DEFAULT 'NORMAL', -- CRITICAL, HIGH, NORMAL, LOW
    business_case_id        UUID REFERENCES bi_business_cases(id),
    task_id                 TEXT,                       -- tasks.task_id (TEXT) if applicable
    so_id                   UUID REFERENCES bi_sales_orders(id),
    description             TEXT NOT NULL,
    evidence                JSONB,
    suggested_action        TEXT,
    owner_employee_id       UUID REFERENCES employees(id),
    status                  TEXT NOT NULL DEFAULT 'OPEN',
    acknowledged_by_employee_id UUID REFERENCES employees(id),
    acknowledged_at         TIMESTAMPTZ,
    resolved_by_employee_id UUID REFERENCES employees(id),
    resolved_at             TIMESTAMPTZ,
    resolution_notes        TEXT,
    dedup_key               TEXT UNIQUE,                -- Prevents duplicate alerts for same issue
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_alerts_severity_check CHECK (
        severity IN ('CRITICAL','HIGH','NORMAL','LOW')
    ),
    CONSTRAINT bi_alerts_status_check CHECK (
        status IN ('OPEN','ACKNOWLEDGED','RESOLVED','SUPPRESSED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_alerts_status ON bi_monitoring_alerts(status);
CREATE INDEX IF NOT EXISTS idx_bi_alerts_type ON bi_monitoring_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_bi_alerts_case ON bi_monitoring_alerts(business_case_id) WHERE business_case_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_alerts_task ON bi_monitoring_alerts(task_id) WHERE task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_alerts_severity ON bi_monitoring_alerts(severity);

-- Audit events
CREATE TABLE IF NOT EXISTS bi_audit_events (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_type              TEXT NOT NULL DEFAULT 'EMPLOYEE',  -- EMPLOYEE, SYSTEM, AI, INTEGRATION
    actor_id                TEXT,                               -- employee UUID or system identifier
    action                  TEXT NOT NULL,                      -- e.g. 'TASK_PROPOSAL_APPROVED'
    entity_type             TEXT NOT NULL,
    entity_id               TEXT NOT NULL,
    before_state_summary    JSONB,                              -- Sanitised; no secrets/bodies
    after_state_summary     JSONB,
    correlation_id          UUID,
    reason                  TEXT,
    ip_address              TEXT,                               -- Null if not available
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_audit_entity ON bi_audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_bi_audit_actor ON bi_audit_events(actor_id) WHERE actor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_audit_action ON bi_audit_events(action);
CREATE INDEX IF NOT EXISTS idx_bi_audit_created ON bi_audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_bi_audit_correlation ON bi_audit_events(correlation_id) WHERE correlation_id IS NOT NULL;

-- Human feedback
CREATE TABLE IF NOT EXISTS bi_human_feedback (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID REFERENCES employees(id),
    entity_type         TEXT NOT NULL,              -- EMAIL_ANALYSIS, BUSINESS_CASE, TASK_PROPOSAL, etc.
    entity_id           TEXT NOT NULL,
    feedback_type       TEXT NOT NULL,              -- CORRECTION, REJECTION, CONFIRMATION, COMMENT
    field_name          TEXT,                       -- Which specific field was corrected
    original_value      JSONB,
    corrected_value     JSONB,
    reason              TEXT,
    source_message_id   UUID REFERENCES bi_source_messages(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    review_status       TEXT NOT NULL DEFAULT 'PENDING',
    CONSTRAINT bi_feedback_type_check CHECK (
        feedback_type IN ('CORRECTION','REJECTION','CONFIRMATION','COMMENT','ESCALATION')
    ),
    CONSTRAINT bi_feedback_review_check CHECK (
        review_status IN ('PENDING','INCORPORATED','DISMISSED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_feedback_entity ON bi_human_feedback(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_bi_feedback_employee ON bi_human_feedback(employee_id) WHERE employee_id IS NOT NULL;

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE bi_task_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_task_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_task_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_task_assignment_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_task_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_dependencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_smart_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_monitoring_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_human_feedback ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'bi_task_proposals','bi_task_metadata','bi_task_sources',
        'bi_task_assignment_history','bi_task_updates','bi_dependencies',
        'bi_smart_drafts','bi_monitoring_alerts','bi_human_feedback'
    ] LOOP
        EXECUTE format(
            'CREATE POLICY "%s_auth_read" ON %s FOR SELECT TO authenticated USING (true)',
            tbl, tbl
        );
        EXECUTE format(
            'CREATE POLICY "%s_service_all" ON %s FOR ALL TO service_role USING (true) WITH CHECK (true)',
            tbl, tbl
        );
    END LOOP;
END;
$$;

-- Audit events: readable by authenticated, only insertable by service (append-only)
CREATE POLICY "bi_audit_auth_read" ON bi_audit_events FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_audit_service_all" ON bi_audit_events FOR ALL TO service_role USING (true) WITH CHECK (true);
