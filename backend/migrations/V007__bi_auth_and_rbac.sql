-- =============================================================================
-- Migration V007: User Authentication, Role-Based Access Control & Audit
-- Created: 2026-11-08
-- Purpose: Additive tables for internal login, role request approvals, sessions,
--          and user audit logs.
-- Existing tables affected: NONE (16 legacy tables untouched)
-- Rollback: See rollback/R007__rollback.sql
-- =============================================================================

-- User Accounts (Internal credentials & profile state)
CREATE TABLE IF NOT EXISTS user_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID REFERENCES employees(id) ON DELETE SET NULL,
    email               TEXT NOT NULL UNIQUE,
    password_hash       TEXT NOT NULL,
    full_name           TEXT NOT NULL,
    department          TEXT NOT NULL,
    requested_position  TEXT NOT NULL DEFAULT 'EMPLOYEE',
    approved_position   TEXT NOT NULL DEFAULT 'EMPLOYEE',
    account_status      TEXT NOT NULL DEFAULT 'active', -- active, pending_approval, rejected, suspended
    rejection_reason    TEXT,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_accounts_status_check CHECK (
        account_status IN ('active', 'pending_approval', 'rejected', 'suspended')
    ),
    CONSTRAINT user_accounts_position_check CHECK (
        approved_position IN ('EMPLOYEE', 'DEPT_HEAD', 'MANAGEMENT', 'SYSADMIN', 'AUDITOR', 'TEAM_LEADER')
    )
);

CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts(email);
CREATE INDEX IF NOT EXISTS idx_user_accounts_employee ON user_accounts(employee_id);
CREATE INDEX IF NOT EXISTS idx_user_accounts_dept ON user_accounts(department);
CREATE INDEX IF NOT EXISTS idx_user_accounts_status ON user_accounts(account_status);

-- Role Requests (Pending approval for HOD, Manager, Administrator)
CREATE TABLE IF NOT EXISTS role_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    requested_position      TEXT NOT NULL,
    requested_department    TEXT NOT NULL,
    approval_status         TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
    reviewed_by             TEXT,
    review_reason           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at             TIMESTAMPTZ,
    CONSTRAINT role_requests_status_check CHECK (
        approval_status IN ('PENDING', 'APPROVED', 'REJECTED')
    )
);

CREATE INDEX IF NOT EXISTS idx_role_requests_user ON role_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_role_requests_status ON role_requests(approval_status);

-- User Sessions (Stateful server-validated sessions)
CREATE TABLE IF NOT EXISTS user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    session_token   TEXT NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    ip_address      TEXT,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);

-- User Audit Logs (Administrative actions, role/department changes, suspensions)
CREATE TABLE IF NOT EXISTS user_audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES user_accounts(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,
    old_value       JSONB,
    new_value       JSONB,
    performed_by    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_audit_logs_user ON user_audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_audit_logs_action ON user_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_user_audit_logs_created ON user_audit_logs(created_at);
