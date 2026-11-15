-- =============================================================================
-- Migration Rollback R008: Multi-User Microsoft Outlook Integration
-- Rollback for V008__multi_user_outlook_integration.sql
-- =============================================================================

DROP TABLE IF EXISTS email_analysis_results CASCADE;
DROP TABLE IF EXISTS email_sync_runs CASCADE;
DROP TABLE IF EXISTS email_folder_sync_state CASCADE;
DROP TABLE IF EXISTS email_messages CASCADE;
DROP TABLE IF EXISTS email_folders CASCADE;
DROP TABLE IF EXISTS microsoft_connections CASCADE;
