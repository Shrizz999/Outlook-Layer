-- Rollback for V003: Email and Intelligence Tables
DROP TABLE IF EXISTS bi_review_queue CASCADE;
DROP TABLE IF EXISTS bi_ai_usage CASCADE;
DROP TABLE IF EXISTS bi_processing_jobs CASCADE;
DROP TABLE IF EXISTS bi_commitments CASCADE;
DROP TABLE IF EXISTS bi_extracted_facts CASCADE;
DROP TABLE IF EXISTS bi_email_analyses CASCADE;
DROP TABLE IF EXISTS bi_source_attachments CASCADE;
DROP TABLE IF EXISTS bi_source_messages CASCADE;
DROP TABLE IF EXISTS bi_conversations CASCADE;
DROP TABLE IF EXISTS bi_source_mailboxes CASCADE;
