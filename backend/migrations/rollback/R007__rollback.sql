-- =============================================================================
-- Rollback R007: Drop V007 Auth and RBAC tables
-- =============================================================================

DROP TABLE IF EXISTS user_audit_logs CASCADE;
DROP TABLE IF EXISTS user_sessions CASCADE;
DROP TABLE IF EXISTS role_requests CASCADE;
DROP TABLE IF EXISTS user_accounts CASCADE;
