-- =============================================================================
-- Migration V002: Balbird Intelligence Business Cases
-- Created: 2026-11-06
-- Purpose: Business Case management — the central coordination entity
-- Existing tables affected: NONE
-- References: employees.id (UUID), bi_customers.id, bi_suppliers.id
-- Rollback: See rollback/R002__rollback.sql
-- =============================================================================

-- Business Cases
CREATE TABLE IF NOT EXISTS bi_business_cases (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number             TEXT NOT NULL UNIQUE,       -- e.g. CASE-2026-00001
    title                   TEXT NOT NULL,
    case_type               TEXT NOT NULL DEFAULT 'ENQUIRY',  -- ENQUIRY, RFQ, ORDER, PROJECT, ISSUE, OTHER
    status                  TEXT NOT NULL DEFAULT 'NEW',
    primary_customer_id     UUID REFERENCES bi_customers(id),
    primary_owner_employee_id UUID REFERENCES employees(id),  -- References existing employees table
    priority                TEXT NOT NULL DEFAULT 'NORMAL',
    opened_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at               TIMESTAMPTZ,
    summary                 TEXT,                       -- AI-generated, clearly labelled
    summary_is_ai_generated BOOLEAN NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_employee_id  UUID REFERENCES employees(id),
    CONSTRAINT bi_business_cases_type_check CHECK (
        case_type IN ('ENQUIRY','RFQ','ORDER','PROJECT','ISSUE','OTHER')
    ),
    CONSTRAINT bi_business_cases_status_check CHECK (
        status IN ('NEW','UNDER_REVIEW','ACTIVE','WAITING_CUSTOMER','WAITING_SUPPLIER',
                   'WAITING_INTERNAL','AT_RISK','ON_HOLD','COMPLETED','CANCELLED','ARCHIVED')
    ),
    CONSTRAINT bi_business_cases_priority_check CHECK (
        priority IN ('CRITICAL','HIGH','NORMAL','LOW')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_bc_number ON bi_business_cases(case_number);
CREATE INDEX IF NOT EXISTS idx_bi_bc_status ON bi_business_cases(status);
CREATE INDEX IF NOT EXISTS idx_bi_bc_customer ON bi_business_cases(primary_customer_id) WHERE primary_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_bc_owner ON bi_business_cases(primary_owner_employee_id) WHERE primary_owner_employee_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_bc_priority ON bi_business_cases(priority);
CREATE INDEX IF NOT EXISTS idx_bi_bc_opened_at ON bi_business_cases(opened_at);

-- Case number sequence helper function
CREATE OR REPLACE FUNCTION bi_next_case_number()
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    current_year TEXT;
    next_seq     INT;
BEGIN
    current_year := to_char(now(), 'YYYY');
    SELECT COALESCE(MAX(
        NULLIF(regexp_replace(case_number, '^CASE-\d{4}-', ''), case_number)::INT
    ), 0) + 1
    INTO next_seq
    FROM bi_business_cases
    WHERE case_number LIKE 'CASE-' || current_year || '-%';
    
    RETURN 'CASE-' || current_year || '-' || lpad(next_seq::TEXT, 5, '0');
END;
$$;

-- Case parties (customers, suppliers, internal teams)
CREATE TABLE IF NOT EXISTS bi_case_parties (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_case_id    UUID NOT NULL REFERENCES bi_business_cases(id) ON DELETE CASCADE,
    party_type          TEXT NOT NULL,              -- CUSTOMER, SUPPLIER, INTERNAL, OTHER
    customer_id         UUID REFERENCES bi_customers(id),
    supplier_id         UUID REFERENCES bi_suppliers(id),
    employee_id         UUID REFERENCES employees(id),
    party_name          TEXT,                       -- Fallback if not in master data
    relationship_role   TEXT,                       -- BUYER, SELLER, MANUFACTURER, LOGISTICS, etc.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_case_parties_type_check CHECK (
        party_type IN ('CUSTOMER','SUPPLIER','INTERNAL','OTHER')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_case_parties_case ON bi_case_parties(business_case_id);
CREATE INDEX IF NOT EXISTS idx_bi_case_parties_customer ON bi_case_parties(customer_id) WHERE customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_case_parties_supplier ON bi_case_parties(supplier_id) WHERE supplier_id IS NOT NULL;

-- Case links (polymorphic association to SO, PO, RFQ, task, message)
CREATE TABLE IF NOT EXISTS bi_case_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_case_id    UUID NOT NULL REFERENCES bi_business_cases(id) ON DELETE CASCADE,
    linked_object_type  TEXT NOT NULL,              -- SO, PO, RFQ, TASK, MESSAGE, PART, etc.
    linked_object_id    TEXT NOT NULL,              -- UUID or TEXT depending on type
    relationship_type   TEXT NOT NULL DEFAULT 'RELATED', -- PRIMARY, RELATED, EVIDENCE, SUPERSEDES
    match_method        TEXT,                       -- EXACT_REF, ALIAS, CONVERSATION, HUMAN, AI_SUGGESTION
    match_confidence    NUMERIC(5,4),               -- 0.0000 to 1.0000
    validation_status   TEXT NOT NULL DEFAULT 'UNREVIEWED',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_employee_id UUID REFERENCES employees(id),
    CONSTRAINT bi_case_links_obj_type_check CHECK (
        linked_object_type IN ('SO','PO','RFQ','TASK','MESSAGE','PART','CUSTOMER','SUPPLIER','WORKFLOW')
    ),
    CONSTRAINT bi_case_links_validation_check CHECK (
        validation_status IN ('UNREVIEWED','ACCEPTED_AUTO','ACCEPTED_HUMAN','REJECTED_HUMAN','NEEDS_REVIEW','SUPERSEDED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_case_links_case ON bi_case_links(business_case_id);
CREATE INDEX IF NOT EXISTS idx_bi_case_links_object ON bi_case_links(linked_object_type, linked_object_id);

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE bi_business_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_case_parties ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_case_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY "bi_business_cases_authenticated_read"
    ON bi_business_cases FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_business_cases_service_all"
    ON bi_business_cases FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_case_parties_authenticated_read"
    ON bi_case_parties FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_case_parties_service_all"
    ON bi_case_parties FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_case_links_authenticated_read"
    ON bi_case_links FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_case_links_service_all"
    ON bi_case_links FOR ALL TO service_role USING (true) WITH CHECK (true);
