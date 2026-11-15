-- Rollback for V006
DROP TABLE IF EXISTS bi_physical_verifications CASCADE;
DROP TABLE IF EXISTS bi_task_handovers CASCADE;
DROP INDEX IF EXISTS idx_bi_dept_active_hod;
DROP TABLE IF EXISTS bi_department_hods CASCADE;
