-- =============================================================================
-- Migration Rollback R009: Email Client Operations, Drafts, Sending Audit & To Do
-- Rollback for V009__email_client_and_todo.sql
-- =============================================================================

DROP TABLE IF EXISTS bi_external_task_mappings CASCADE;
DROP TABLE IF EXISTS email_send_audit_events CASCADE;
DROP TABLE IF EXISTS email_drafts CASCADE;

ALTER TABLE email_messages
    DROP COLUMN IF EXISTS is_flagged,
    DROP COLUMN IF EXISTS flag_status,
    DROP COLUMN IF EXISTS categories,
    DROP COLUMN IF EXISTS send_status,
    DROP COLUMN IF EXISTS send_error,
    DROP COLUMN IF EXISTS in_reply_to_id,
    DROP COLUMN IF EXISTS reply_to_recipients,
    DROP COLUMN IF EXISTS bcc_recipients,
    DROP COLUMN IF EXISTS idempotency_key;
