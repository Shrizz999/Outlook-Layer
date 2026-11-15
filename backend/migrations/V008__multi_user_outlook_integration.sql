-- =============================================================================
-- Migration V008: Multi-User Microsoft Outlook Integration for Balbird Intelligence
-- Created: 2026-11-09
-- Purpose: Support multi-user Microsoft 365 / Personal Outlook connections,
--          recursive folder discovery, delta synchronization, encrypted token
--          storage, and email intelligence mapping with strict data isolation.
-- Existing tables affected: NONE (additive only)
-- References: employees.id (UUID)
-- Rollback: See rollback/R008__rollback.sql
-- =============================================================================

-- 1. Microsoft Connections (per employee)
CREATE TABLE IF NOT EXISTS microsoft_connections (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id             UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    microsoft_user_id       TEXT NOT NULL,
    tenant_id               TEXT,                             -- Nullable for personal accounts (live.com / hotmail)
    email_address           TEXT NOT NULL,
    display_name            TEXT,
    account_type            TEXT NOT NULL DEFAULT 'organizational', -- 'organizational', 'personal'
    encrypted_token_cache   TEXT NOT NULL,                   -- Server-side AES/Fernet encrypted MSAL token cache
    granted_scopes          JSONB NOT NULL DEFAULT '[]',
    connection_status       TEXT NOT NULL DEFAULT 'active',   -- 'active', 'expired', 'error', 'disconnected', 'reauth_required'
    connected_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_synced_at          TIMESTAMPTZ,
    last_error              TEXT,
    disconnected_at         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ms_connections_user UNIQUE (microsoft_user_id),
    CONSTRAINT chk_ms_connection_status CHECK (
        connection_status IN ('active', 'expired', 'error', 'disconnected', 'reauth_required')
    ),
    CONSTRAINT chk_ms_account_type CHECK (
        account_type IN ('organizational', 'personal')
    )
);

CREATE INDEX IF NOT EXISTS idx_ms_conn_employee ON microsoft_connections(employee_id);
CREATE INDEX IF NOT EXISTS idx_ms_conn_email ON microsoft_connections(email_address);
CREATE INDEX IF NOT EXISTS idx_ms_conn_status ON microsoft_connections(connection_status);

-- 2. Mailbox Folders (recursive folder hierarchy)
CREATE TABLE IF NOT EXISTS email_folders (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id           UUID NOT NULL REFERENCES microsoft_connections(id) ON DELETE CASCADE,
    graph_folder_id         TEXT NOT NULL,
    parent_folder_id        TEXT,                             -- Graph ID of parent folder if nested
    display_name            TEXT NOT NULL,
    well_known_name         TEXT,                             -- 'inbox', 'sentitems', 'archive', 'deleteditems', etc.
    is_hidden               BOOLEAN NOT NULL DEFAULT false,
    is_system_folder        BOOLEAN NOT NULL DEFAULT false,
    sync_enabled            BOOLEAN NOT NULL DEFAULT true,
    total_item_count        INT NOT NULL DEFAULT 0,
    unread_item_count       INT NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_email_folders_graph_id UNIQUE (connection_id, graph_folder_id)
);

CREATE INDEX IF NOT EXISTS idx_email_folders_conn ON email_folders(connection_id);
CREATE INDEX IF NOT EXISTS idx_email_folders_parent ON email_folders(connection_id, parent_folder_id);
CREATE INDEX IF NOT EXISTS idx_email_folders_sync ON email_folders(connection_id, sync_enabled);

-- 3. Email Messages (synchronized messages with immutable ID preferences)
CREATE TABLE IF NOT EXISTS email_messages (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id           UUID NOT NULL REFERENCES microsoft_connections(id) ON DELETE CASCADE,
    employee_id             UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    folder_id               UUID REFERENCES email_folders(id) ON DELETE SET NULL,
    graph_message_id        TEXT NOT NULL,
    internet_message_id     TEXT,
    conversation_id         TEXT,
    subject                 TEXT,
    sender_name             TEXT,
    sender_email            TEXT,
    recipients              JSONB NOT NULL DEFAULT '[]',      -- [{name, email}]
    cc_recipients           JSONB NOT NULL DEFAULT '[]',      -- [{name, email}]
    received_at             TIMESTAMPTZ,
    sent_at                 TIMESTAMPTZ,
    body_content            TEXT,                             -- Sanitized body content
    body_type               TEXT NOT NULL DEFAULT 'html',     -- 'html', 'text'
    body_preview            TEXT,
    has_attachments         BOOLEAN NOT NULL DEFAULT false,
    importance              TEXT NOT NULL DEFAULT 'normal',   -- 'low', 'normal', 'high'
    is_read                 BOOLEAN NOT NULL DEFAULT false,
    is_draft                BOOLEAN NOT NULL DEFAULT false,
    is_deleted              BOOLEAN NOT NULL DEFAULT false,   -- Soft-delete for moved/removed messages
    web_link                TEXT,
    last_modified_at        TIMESTAMPTZ,
    source                  TEXT NOT NULL DEFAULT 'MICROSOFT_GRAPH',
    content_hash            TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_email_messages_graph_id UNIQUE (connection_id, graph_message_id)
);

CREATE INDEX IF NOT EXISTS idx_email_msgs_conn ON email_messages(connection_id);
CREATE INDEX IF NOT EXISTS idx_email_msgs_employee ON email_messages(employee_id);
CREATE INDEX IF NOT EXISTS idx_email_msgs_folder ON email_messages(folder_id);
CREATE INDEX IF NOT EXISTS idx_email_msgs_received ON email_messages(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_msgs_conversation ON email_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_email_msgs_internet_id ON email_messages(internet_message_id);
CREATE INDEX IF NOT EXISTS idx_email_msgs_hash ON email_messages(content_hash);
CREATE INDEX IF NOT EXISTS idx_email_msgs_is_deleted ON email_messages(is_deleted);

-- 4. Folder Sync State (tracking opaque Graph delta links per folder)
CREATE TABLE IF NOT EXISTS email_folder_sync_state (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id           UUID NOT NULL REFERENCES microsoft_connections(id) ON DELETE CASCADE,
    folder_id               UUID NOT NULL REFERENCES email_folders(id) ON DELETE CASCADE,
    delta_link              TEXT,                             -- Opaque Graph delta continuation token
    next_link               TEXT,                             -- Opaque Graph pagination token
    last_successful_sync    TIMESTAMPTZ,
    last_attempted_sync     TIMESTAMPTZ,
    sync_status             TEXT NOT NULL DEFAULT 'idle',     -- 'idle', 'syncing', 'completed', 'error', 'expired'
    last_error              TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_folder_sync_state UNIQUE (folder_id),
    CONSTRAINT chk_folder_sync_status CHECK (
        sync_status IN ('idle', 'syncing', 'completed', 'error', 'expired')
    )
);

CREATE INDEX IF NOT EXISTS idx_sync_state_conn ON email_folder_sync_state(connection_id);
CREATE INDEX IF NOT EXISTS idx_sync_state_status ON email_folder_sync_state(sync_status);

-- 5. Email Sync Runs (audit trail for synchronization jobs)
CREATE TABLE IF NOT EXISTS email_sync_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id           UUID NOT NULL REFERENCES microsoft_connections(id) ON DELETE CASCADE,
    sync_type               TEXT NOT NULL DEFAULT 'DELTA',    -- 'INITIAL', 'DELTA', 'MANUAL'
    status                  TEXT NOT NULL DEFAULT 'RUNNING',  -- 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED'
    started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at            TIMESTAMPTZ,
    messages_discovered     INTEGER NOT NULL DEFAULT 0,
    messages_inserted       INTEGER NOT NULL DEFAULT 0,
    messages_updated        INTEGER NOT NULL DEFAULT 0,
    messages_deleted        INTEGER NOT NULL DEFAULT 0,
    errors_count            INTEGER NOT NULL DEFAULT 0,
    error_summary           TEXT,
    CONSTRAINT chk_sync_run_status CHECK (
        status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')
    )
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_conn ON email_sync_runs(connection_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON email_sync_runs(started_at DESC);

-- 6. Email Analysis Results (isolated AI proposals & extracted business intelligence)
CREATE TABLE IF NOT EXISTS email_analysis_results (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_message_id        UUID NOT NULL REFERENCES email_messages(id) ON DELETE CASCADE,
    analysis_status         TEXT NOT NULL DEFAULT 'PENDING',  -- 'PENDING', 'COMPLETED', 'FAILED', 'SKIPPED'
    classification          TEXT NOT NULL DEFAULT 'UNCLASSIFIED', -- 'PERSONAL', 'BUSINESS', 'SENSITIVE', 'UNCLASSIFIED'
    business_relevance      TEXT NOT NULL DEFAULT 'UNKNOWN',  -- 'HIGH', 'MEDIUM', 'LOW', 'NONE', 'UNKNOWN'
    summary                 TEXT,
    extracted_entities      JSONB NOT NULL DEFAULT '{}',
    extracted_actions       JSONB NOT NULL DEFAULT '[]',
    extracted_dates         JSONB NOT NULL DEFAULT '[]',
    extracted_commitments   JSONB NOT NULL DEFAULT '[]',
    confidence              NUMERIC(5,4),
    evidence                JSONB NOT NULL DEFAULT '{}',
    model_provider          TEXT,
    model_name              TEXT,
    prompt_version          TEXT,
    human_review_status     TEXT NOT NULL DEFAULT 'UNREVIEWED', -- 'UNREVIEWED', 'ACCEPTED', 'REJECTED'
    reviewed_by             UUID REFERENCES employees(id),
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_email_analysis_msg UNIQUE (email_message_id),
    CONSTRAINT chk_analysis_status CHECK (
        analysis_status IN ('PENDING', 'COMPLETED', 'FAILED', 'SKIPPED')
    ),
    CONSTRAINT chk_analysis_classification CHECK (
        classification IN ('PERSONAL', 'BUSINESS', 'SENSITIVE', 'UNCLASSIFIED')
    )
);

CREATE INDEX IF NOT EXISTS idx_analysis_msg ON email_analysis_results(email_message_id);
CREATE INDEX IF NOT EXISTS idx_analysis_status ON email_analysis_results(analysis_status);
CREATE INDEX IF NOT EXISTS idx_analysis_relevance ON email_analysis_results(business_relevance);

-- =============================================================================
-- Row Level Security (RLS)
-- =============================================================================

ALTER TABLE microsoft_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_folder_sync_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_sync_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_analysis_results ENABLE ROW LEVEL SECURITY;

-- Service role bypass for backend background sync jobs
CREATE POLICY "ms_conn_service_all" ON microsoft_connections FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "email_folders_service_all" ON email_folders FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "email_messages_service_all" ON email_messages FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "sync_state_service_all" ON email_folder_sync_state FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "sync_runs_service_all" ON email_sync_runs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "email_analysis_service_all" ON email_analysis_results FOR ALL TO service_role USING (true) WITH CHECK (true);
