-- =============================================================================
-- Migration V009: Email Client Operations, Drafts, Sending Audit & Microsoft To Do
-- Created: 2026-11-10
-- Purpose: Add native email client functionality to Balbird:
--          1. Message flags, categories, reply tracking, and send status.
--          2. Draft auto-save and management table (email_drafts).
--          3. Outbound email send audit trail (email_send_audit_events).
--          4. Microsoft To Do external task synchronization (bi_external_task_mappings).
-- Existing tables affected: email_messages (additive columns only)
-- Rollback: See rollback/R009__rollback.sql
-- =============================================================================

-- 1. Extend email_messages with client flags, categories, and sending tracking
ALTER TABLE email_messages
    ADD COLUMN IF NOT EXISTS is_flagged BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS flag_status TEXT NOT NULL DEFAULT 'notFlagged',
    ADD COLUMN IF NOT EXISTS categories JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS send_status TEXT NOT NULL DEFAULT 'synced',
    ADD COLUMN IF NOT EXISTS send_error TEXT,
    ADD COLUMN IF NOT EXISTS in_reply_to_id TEXT,
    ADD COLUMN IF NOT EXISTS reply_to_recipients JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS bcc_recipients JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

CREATE INDEX IF NOT EXISTS idx_email_msgs_is_flagged ON email_messages(is_flagged);
CREATE INDEX IF NOT EXISTS idx_email_msgs_send_status ON email_messages(send_status);
CREATE INDEX IF NOT EXISTS idx_email_msgs_idempotency ON email_messages(idempotency_key);

-- 2. Drafts table for auto-save and composer state
CREATE TABLE IF NOT EXISTS email_drafts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id           UUID NOT NULL REFERENCES microsoft_connections(id) ON DELETE CASCADE,
    employee_id             UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    graph_draft_id          TEXT,
    reply_to_message_id     UUID REFERENCES email_messages(id) ON DELETE SET NULL,
    reply_mode              TEXT NOT NULL DEFAULT 'new',      -- 'new', 'reply', 'reply_all', 'forward'
    subject                 TEXT NOT NULL DEFAULT '',
    to_recipients           JSONB NOT NULL DEFAULT '[]',      -- [{name, email}]
    cc_recipients           JSONB NOT NULL DEFAULT '[]',      -- [{name, email}]
    bcc_recipients          JSONB NOT NULL DEFAULT '[]',      -- [{name, email}]
    body_content            TEXT NOT NULL DEFAULT '',
    body_type               TEXT NOT NULL DEFAULT 'html',     -- 'html', 'text'
    importance              TEXT NOT NULL DEFAULT 'normal',   -- 'low', 'normal', 'high'
    status                  TEXT NOT NULL DEFAULT 'draft',    -- 'draft', 'saving', 'sending', 'sent', 'discarded', 'error'
    last_saved_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_email_draft_reply_mode CHECK (
        reply_mode IN ('new', 'reply', 'reply_all', 'forward')
    ),
    CONSTRAINT chk_email_draft_status CHECK (
        status IN ('draft', 'saving', 'sending', 'sent', 'discarded', 'error')
    )
);

CREATE INDEX IF NOT EXISTS idx_email_drafts_conn ON email_drafts(connection_id);
CREATE INDEX IF NOT EXISTS idx_email_drafts_employee ON email_drafts(employee_id);
CREATE INDEX IF NOT EXISTS idx_email_drafts_reply_to ON email_drafts(reply_to_message_id);
CREATE INDEX IF NOT EXISTS idx_email_drafts_status ON email_drafts(status);
CREATE INDEX IF NOT EXISTS idx_email_drafts_updated ON email_drafts(updated_at DESC);

-- 3. Outbound email sending audit trail
CREATE TABLE IF NOT EXISTS email_send_audit_events (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id               UUID NOT NULL REFERENCES microsoft_connections(id) ON DELETE CASCADE,
    employee_id                 UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    draft_id                    UUID REFERENCES email_drafts(id) ON DELETE SET NULL,
    sent_message_id             UUID REFERENCES email_messages(id) ON DELETE SET NULL,
    sender_email                TEXT NOT NULL,
    recipients                  JSONB NOT NULL DEFAULT '[]',
    cc_recipients               JSONB NOT NULL DEFAULT '[]',
    bcc_recipients              JSONB NOT NULL DEFAULT '[]',
    subject                     TEXT NOT NULL,
    action_type                 TEXT NOT NULL DEFAULT 'send', -- 'send', 'reply', 'reply_all', 'forward'
    idempotency_key             TEXT NOT NULL,
    status                      TEXT NOT NULL,               -- 'initiated', 'graph_accepted', 'failed'
    graph_internet_message_id   TEXT,
    error_message               TEXT,
    initiated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at                TIMESTAMPTZ,
    CONSTRAINT chk_email_send_audit_action CHECK (
        action_type IN ('send', 'reply', 'reply_all', 'forward')
    ),
    CONSTRAINT chk_email_send_audit_status CHECK (
        status IN ('initiated', 'graph_accepted', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_email_send_audit_conn ON email_send_audit_events(connection_id);
CREATE INDEX IF NOT EXISTS idx_email_send_audit_emp ON email_send_audit_events(employee_id);
CREATE INDEX IF NOT EXISTS idx_email_send_audit_idempotency ON email_send_audit_events(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_email_send_audit_initiated ON email_send_audit_events(initiated_at DESC);

-- 4. External task mapping (e.g. Microsoft To Do)
CREATE TABLE IF NOT EXISTS bi_external_task_mappings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             TEXT NOT NULL,                                -- References tasks.task_id (TEXT)
    connection_id       UUID NOT NULL REFERENCES microsoft_connections(id) ON DELETE CASCADE,
    provider            TEXT NOT NULL DEFAULT 'microsoft_todo',
    external_list_id    TEXT NOT NULL,
    external_task_id    TEXT NOT NULL,
    title               TEXT NOT NULL,
    due_date            TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'notStarted',
    external_url        TEXT,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_external_task_mapping UNIQUE (provider, external_task_id)
);

CREATE INDEX IF NOT EXISTS idx_ext_task_map_task ON bi_external_task_mappings(task_id);
CREATE INDEX IF NOT EXISTS idx_ext_task_map_conn ON bi_external_task_mappings(connection_id);
