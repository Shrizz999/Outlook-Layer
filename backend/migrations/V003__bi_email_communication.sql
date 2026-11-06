-- =============================================================================
-- Migration V003: Balbird Intelligence Email / Communication Tables
-- Created: 2026-11-06
-- Purpose: Source mailboxes, messages, attachments, conversations, analyses,
--          extracted facts, commitments, and processing jobs
-- Existing tables affected: NONE
-- References: employees.id (UUID), bi_business_cases.id
-- Rollback: See rollback/R003__rollback.sql
-- =============================================================================

-- Source mailboxes
CREATE TABLE IF NOT EXISTS bi_source_mailboxes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider            TEXT NOT NULL DEFAULT 'FIXTURE',  -- FIXTURE, MICROSOFT_GRAPH
    tenant_reference    TEXT,                             -- Non-secret tenant identifier
    mailbox_reference   TEXT,                             -- Protected; not logged
    display_name        TEXT NOT NULL,
    sync_mode           TEXT NOT NULL DEFAULT 'MANUAL',   -- MANUAL, DELTA, SUBSCRIPTION
    permission_profile  TEXT NOT NULL DEFAULT 'READ_ONLY',
    is_enabled          BOOLEAN NOT NULL DEFAULT false,   -- Disabled by default; must be explicitly enabled
    last_sync_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_source_mailboxes_provider_check CHECK (
        provider IN ('FIXTURE','MICROSOFT_GRAPH')
    ),
    CONSTRAINT bi_source_mailboxes_sync_check CHECK (
        sync_mode IN ('MANUAL','DELTA','SUBSCRIPTION')
    ),
    CONSTRAINT bi_source_mailboxes_perm_check CHECK (
        permission_profile IN ('READ_ONLY','READ_CATEGORISE','READ_WRITE')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_mailboxes_provider ON bi_source_mailboxes(provider);

-- Conversations / threads
CREATE TABLE IF NOT EXISTS bi_conversations (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_mailbox_id           UUID NOT NULL REFERENCES bi_source_mailboxes(id),
    provider_conversation_id    TEXT,               -- Provider-native conversation/thread ID
    subject_normalised          TEXT,               -- Normalised subject for grouping
    first_message_at            TIMESTAMPTZ,
    last_message_at             TIMESTAMPTZ,
    message_count               INT NOT NULL DEFAULT 0,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_conversations_mailbox ON bi_conversations(source_mailbox_id);
CREATE INDEX IF NOT EXISTS idx_bi_conversations_provider_id ON bi_conversations(provider_conversation_id) WHERE provider_conversation_id IS NOT NULL;

-- Source messages
CREATE TABLE IF NOT EXISTS bi_source_messages (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_mailbox_id           UUID NOT NULL REFERENCES bi_source_mailboxes(id),
    conversation_id             UUID REFERENCES bi_conversations(id),
    provider_message_id         TEXT,               -- Provider-native message ID
    internet_message_id         TEXT,               -- RFC 2822 Message-ID header
    subject                     TEXT,
    sender_address              TEXT,
    sender_display_name         TEXT,
    to_recipients               JSONB NOT NULL DEFAULT '[]',  -- [{address, display_name}]
    cc_recipients               JSONB NOT NULL DEFAULT '[]',
    sent_at                     TIMESTAMPTZ,
    received_at                 TIMESTAMPTZ,
    body_text                   TEXT,               -- Nullable; retention-controlled
    body_preprocessed           TEXT,               -- Cleaned body without quoted history
    quoted_history_text         TEXT,               -- Separated quoted history
    signature_text              TEXT,               -- Detected signature
    body_hash                   TEXT,               -- SHA-256 of body_text for dedup/change detection
    has_attachments             BOOLEAN NOT NULL DEFAULT false,
    is_automated_notification   BOOLEAN NOT NULL DEFAULT false,
    is_read_only_source         BOOLEAN NOT NULL DEFAULT true,
    processing_status           TEXT NOT NULL DEFAULT 'PENDING',
    source_web_link             TEXT,               -- Only if permitted
    fixture_path                TEXT,               -- Source fixture file for synthetic data
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_messages_unique_provider UNIQUE (source_mailbox_id, provider_message_id),
    CONSTRAINT bi_messages_status_check CHECK (
        processing_status IN (
            'PENDING','PREPROCESSING','PREPROCESSED','QUEUED_FOR_ANALYSIS',
            'ANALYSING','ANALYSED','NEEDS_REVIEW','ANALYSIS_FAILED',
            'WAITING_FOR_PROVIDER_QUOTA','DEAD_LETTER','SKIPPED'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_messages_mailbox ON bi_source_messages(source_mailbox_id);
CREATE INDEX IF NOT EXISTS idx_bi_messages_conversation ON bi_source_messages(conversation_id) WHERE conversation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_messages_sender ON bi_source_messages(sender_address);
CREATE INDEX IF NOT EXISTS idx_bi_messages_sent_at ON bi_source_messages(sent_at);
CREATE INDEX IF NOT EXISTS idx_bi_messages_status ON bi_source_messages(processing_status);
CREATE INDEX IF NOT EXISTS idx_bi_messages_internet_id ON bi_source_messages(internet_message_id) WHERE internet_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_messages_body_hash ON bi_source_messages(body_hash) WHERE body_hash IS NOT NULL;

-- Source attachments (metadata only unless approved)
CREATE TABLE IF NOT EXISTS bi_source_attachments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_message_id       UUID NOT NULL REFERENCES bi_source_messages(id) ON DELETE CASCADE,
    provider_attachment_id  TEXT,
    filename                TEXT NOT NULL,
    content_type            TEXT,
    size_bytes              BIGINT,
    content_hash            TEXT,
    storage_reference       TEXT,       -- Protected storage path; null if not retained
    processing_status       TEXT NOT NULL DEFAULT 'METADATA_ONLY',
    retention_status        TEXT NOT NULL DEFAULT 'PENDING_POLICY',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_attachments_proc_check CHECK (
        processing_status IN ('METADATA_ONLY','RETAINED','PROCESSED','DELETED','NOT_PERMITTED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_attachments_message ON bi_source_attachments(source_message_id);

-- Email analyses (AI output per message)
CREATE TABLE IF NOT EXISTS bi_email_analyses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_message_id       UUID NOT NULL REFERENCES bi_source_messages(id),
    analysis_version        INT NOT NULL DEFAULT 1,
    model_provider          TEXT,                   -- e.g. 'openrouter', 'mock'
    model_name              TEXT,                   -- e.g. 'mistralai/mistral-7b-instruct:free'
    prompt_version          TEXT,                   -- e.g. 'email_analysis_v1.0'
    schema_version          TEXT,                   -- e.g. '1.0'
    department              TEXT,
    domain                  TEXT,
    intent                  TEXT,
    language                TEXT,
    priority                TEXT,
    summary                 TEXT,
    requires_action         BOOLEAN,
    follow_up_required      BOOLEAN,
    follow_up_type          TEXT,
    confidence              NUMERIC(5,4),
    validation_status       TEXT NOT NULL DEFAULT 'UNREVIEWED',
    raw_structured_output   JSONB,                  -- Sanitised model output
    processing_duration_ms  INT,
    token_usage             JSONB,                  -- {prompt_tokens, completion_tokens, total_tokens}
    error_class             TEXT,                   -- Null on success; error category on failure
    processed_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_analyses_validation_check CHECK (
        validation_status IN ('UNREVIEWED','ACCEPTED_AUTO','ACCEPTED_HUMAN','REJECTED_HUMAN','NEEDS_REVIEW','SUPERSEDED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_analyses_message ON bi_email_analyses(source_message_id);
CREATE INDEX IF NOT EXISTS idx_bi_analyses_status ON bi_email_analyses(validation_status);
CREATE INDEX IF NOT EXISTS idx_bi_analyses_domain ON bi_email_analyses(domain);
CREATE INDEX IF NOT EXISTS idx_bi_analyses_intent ON bi_email_analyses(intent);

-- Extracted facts (individual assertions from messages)
CREATE TABLE IF NOT EXISTS bi_extracted_facts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_message_id       UUID NOT NULL REFERENCES bi_source_messages(id),
    email_analysis_id       UUID REFERENCES bi_email_analyses(id),
    business_case_id        UUID REFERENCES bi_business_cases(id),  -- Nullable until matched
    fact_type               TEXT NOT NULL,          -- PARTY, REFERENCE, DATE, QUANTITY, ACTION, COMMITMENT, etc.
    subject_entity_type     TEXT,                   -- CUSTOMER, SUPPLIER, PART, SO, PO, etc.
    subject_entity_id       TEXT,                   -- UUID or reference depending on entity type
    predicate               TEXT NOT NULL,          -- e.g. 'promised_delivery_date', 'requested_quantity'
    value                   TEXT,                   -- Raw extracted value
    normalised_value        TEXT,                   -- Cleaned/normalised value
    unit                    TEXT,                   -- Units if applicable
    asserted_by_party_type  TEXT,                   -- CUSTOMER, SUPPLIER, EMPLOYEE, AI
    asserted_by_party_id    TEXT,                   -- Reference to asserted party
    effective_at            TIMESTAMPTZ,            -- When this fact applies/applies from
    confidence              NUMERIC(5,4),
    validation_status       TEXT NOT NULL DEFAULT 'UNREVIEWED',
    evidence_text           TEXT,                   -- Source excerpt supporting this fact
    evidence_location       TEXT,                   -- Where in the message (body, subject, etc.)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    supersedes_fact_id      UUID REFERENCES bi_extracted_facts(id),  -- Chain of corrections
    CONSTRAINT bi_facts_validation_check CHECK (
        validation_status IN ('UNREVIEWED','ACCEPTED_AUTO','ACCEPTED_HUMAN','REJECTED_HUMAN','NEEDS_REVIEW','SUPERSEDED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_facts_message ON bi_extracted_facts(source_message_id);
CREATE INDEX IF NOT EXISTS idx_bi_facts_case ON bi_extracted_facts(business_case_id) WHERE business_case_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_facts_type ON bi_extracted_facts(fact_type);
CREATE INDEX IF NOT EXISTS idx_bi_facts_entity ON bi_extracted_facts(subject_entity_type, subject_entity_id) WHERE subject_entity_id IS NOT NULL;

-- Commitments (promises/expectations from parties)
CREATE TABLE IF NOT EXISTS bi_commitments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_case_id    UUID NOT NULL REFERENCES bi_business_cases(id),
    source_message_id   UUID REFERENCES bi_source_messages(id),
    party_type          TEXT NOT NULL,              -- CUSTOMER, SUPPLIER, EMPLOYEE, OTHER
    customer_id         UUID REFERENCES bi_customers(id),
    supplier_id         UUID REFERENCES bi_suppliers(id),
    employee_id         UUID REFERENCES employees(id),
    commitment_type     TEXT NOT NULL,              -- DELIVERY_DATE, QUANTITY, SCHEDULE, APPROVAL, OTHER
    description         TEXT NOT NULL,
    committed_date      DATE,
    committed_quantity  NUMERIC(18,6),
    unit_of_measure     TEXT,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    confidence          NUMERIC(5,4),
    validation_status   TEXT NOT NULL DEFAULT 'UNREVIEWED',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_commitments_party_check CHECK (
        party_type IN ('CUSTOMER','SUPPLIER','EMPLOYEE','OTHER')
    ),
    CONSTRAINT bi_commitments_status_check CHECK (
        status IN ('PENDING','FULFILLED','BREACHED','SUPERSEDED','CANCELLED')
    ),
    CONSTRAINT bi_commitments_validation_check CHECK (
        validation_status IN ('UNREVIEWED','ACCEPTED_HUMAN','REJECTED_HUMAN','NEEDS_REVIEW')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_commitments_case ON bi_commitments(business_case_id);
CREATE INDEX IF NOT EXISTS idx_bi_commitments_message ON bi_commitments(source_message_id) WHERE source_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_commitments_status ON bi_commitments(status);

-- Processing jobs (background work queue)
CREATE TABLE IF NOT EXISTS bi_processing_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type            TEXT NOT NULL,              -- EMAIL_PREPROCESS, EMAIL_ANALYSE, IMPORT_PREVIEW, etc.
    correlation_id      UUID NOT NULL DEFAULT gen_random_uuid(),
    entity_type         TEXT,                       -- MESSAGE, IMPORT_BATCH, etc.
    entity_id           TEXT,                       -- ID of entity being processed
    status              TEXT NOT NULL DEFAULT 'QUEUED',
    attempt_count       INT NOT NULL DEFAULT 0,
    max_attempts        INT NOT NULL DEFAULT 3,
    priority            INT NOT NULL DEFAULT 5,     -- Lower = higher priority
    scheduled_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    next_retry_at       TIMESTAMPTZ,
    error_message       TEXT,
    error_class         TEXT,
    result_summary      JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_jobs_status_check CHECK (
        status IN ('QUEUED','RUNNING','COMPLETED','FAILED','DEAD_LETTER',
                   'WAITING_FOR_PROVIDER_QUOTA','CANCELLED','SKIPPED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_jobs_status ON bi_processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_bi_jobs_type ON bi_processing_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_bi_jobs_entity ON bi_processing_jobs(entity_type, entity_id) WHERE entity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_jobs_scheduled ON bi_processing_jobs(scheduled_at) WHERE status = 'QUEUED';
CREATE INDEX IF NOT EXISTS idx_bi_jobs_correlation ON bi_processing_jobs(correlation_id);

-- AI provider usage tracking (quota management)
CREATE TABLE IF NOT EXISTS bi_ai_usage (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usage_date      DATE NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    request_count   INT NOT NULL DEFAULT 0,
    prompt_tokens   BIGINT NOT NULL DEFAULT 0,
    completion_tokens BIGINT NOT NULL DEFAULT 0,
    error_count     INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_ai_usage_unique UNIQUE (usage_date, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_bi_ai_usage_date ON bi_ai_usage(usage_date);
CREATE INDEX IF NOT EXISTS idx_bi_ai_usage_provider ON bi_ai_usage(provider, model);

-- Review queue (items needing human attention)
CREATE TABLE IF NOT EXISTS bi_review_queue (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_type          TEXT NOT NULL,              -- CASE_MATCH, TASK_PROPOSAL, ANALYSIS, IMPORT_ROW, etc.
    entity_type         TEXT NOT NULL,
    entity_id           TEXT NOT NULL,
    business_case_id    UUID REFERENCES bi_business_cases(id),
    reason              TEXT NOT NULL,
    priority            TEXT NOT NULL DEFAULT 'NORMAL',
    status              TEXT NOT NULL DEFAULT 'PENDING',
    assigned_to_employee_id UUID REFERENCES employees(id),
    resolved_by_employee_id UUID REFERENCES employees(id),
    resolved_at         TIMESTAMPTZ,
    resolution          TEXT,
    resolution_notes    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_review_status_check CHECK (
        status IN ('PENDING','IN_REVIEW','RESOLVED','SKIPPED','ESCALATED')
    ),
    CONSTRAINT bi_review_queue_type_check CHECK (
        queue_type IN ('CASE_MATCH','TASK_PROPOSAL','ANALYSIS','IMPORT_ROW',
                       'COMMITMENT','DEPENDENCY','ALERT','OTHER')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_review_status ON bi_review_queue(status);
CREATE INDEX IF NOT EXISTS idx_bi_review_type ON bi_review_queue(queue_type);
CREATE INDEX IF NOT EXISTS idx_bi_review_case ON bi_review_queue(business_case_id) WHERE business_case_id IS NOT NULL;

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE bi_source_mailboxes ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_source_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_source_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_email_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_extracted_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_commitments ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_ai_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_review_queue ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read (body content restricted by application layer)
CREATE POLICY "bi_mailboxes_auth_read" ON bi_source_mailboxes FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_mailboxes_service_all" ON bi_source_mailboxes FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_conversations_auth_read" ON bi_conversations FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_conversations_service_all" ON bi_conversations FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_messages_auth_read" ON bi_source_messages FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_messages_service_all" ON bi_source_messages FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_attachments_auth_read" ON bi_source_attachments FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_attachments_service_all" ON bi_source_attachments FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_analyses_auth_read" ON bi_email_analyses FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_analyses_service_all" ON bi_email_analyses FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_facts_auth_read" ON bi_extracted_facts FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_facts_service_all" ON bi_extracted_facts FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_commitments_auth_read" ON bi_commitments FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_commitments_service_all" ON bi_commitments FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_jobs_auth_read" ON bi_processing_jobs FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_jobs_service_all" ON bi_processing_jobs FOR ALL TO service_role USING (true) WITH CHECK (true);

-- AI usage: restricted to service_role and admins (no general user access)
CREATE POLICY "bi_ai_usage_service_all" ON bi_ai_usage FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "bi_review_auth_read" ON bi_review_queue FOR SELECT TO authenticated USING (true);
CREATE POLICY "bi_review_service_all" ON bi_review_queue FOR ALL TO service_role USING (true) WITH CHECK (true);
