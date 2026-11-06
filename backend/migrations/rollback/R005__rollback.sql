-- Rollback for V005: Tasks, Dependencies, Drafts, and Monitoring
DROP TABLE IF EXISTS bi_human_feedback CASCADE;
DROP TABLE IF EXISTS bi_audit_events CASCADE;
DROP TABLE IF EXISTS bi_monitoring_alerts CASCADE;
DROP TABLE IF EXISTS bi_smart_drafts CASCADE;
DROP TABLE IF EXISTS bi_dependencies CASCADE;
DROP TABLE IF EXISTS bi_task_updates CASCADE;
DROP TABLE IF EXISTS bi_task_assignment_history CASCADE;
DROP TABLE IF EXISTS bi_task_sources CASCADE;
DROP TABLE IF EXISTS bi_task_metadata CASCADE;
DROP TABLE IF EXISTS bi_task_proposals CASCADE;
