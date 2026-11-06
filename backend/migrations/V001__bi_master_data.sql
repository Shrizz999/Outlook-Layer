-- =============================================================================
-- Migration V001: Balbird Intelligence Master Data Tables
-- Created: 2026-11-06
-- Purpose: Core reference tables for departments, user profiles, customers,
--          suppliers, and parts. All prefixed bi_ to protect existing schema.
-- Existing tables affected: NONE
-- References: employees.id (UUID) - read only
-- Rollback: See rollback/R001__rollback.sql
-- =============================================================================

-- Departments (BI-managed, separate from employees.department text field)
CREATE TABLE IF NOT EXISTS bi_departments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,           -- e.g. 'SALES', 'PURCHASE', 'PPC'
    name        TEXT NOT NULL,                  -- e.g. 'Sales Department'
    parent_id   UUID REFERENCES bi_departments(id),
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_departments_code ON bi_departments(code);
CREATE INDEX IF NOT EXISTS idx_bi_departments_parent ON bi_departments(parent_id) WHERE parent_id IS NOT NULL;

-- User profiles — extends existing employees table with BI roles/permissions
-- Does NOT modify the employees table
CREATE TABLE IF NOT EXISTS bi_user_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
    bi_role         TEXT NOT NULL DEFAULT 'EMPLOYEE',  -- EMPLOYEE, TEAM_LEADER, DEPT_HEAD, MANAGEMENT, SYSADMIN, AUDITOR
    department_id   UUID REFERENCES bi_departments(id),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_user_profiles_employee_unique UNIQUE (employee_id),
    CONSTRAINT bi_user_profiles_role_check CHECK (
        bi_role IN ('EMPLOYEE','TEAM_LEADER','DEPT_HEAD','MANAGEMENT','SYSADMIN','AUDITOR','INTEGRATION_SERVICE')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_user_profiles_employee ON bi_user_profiles(employee_id);
CREATE INDEX IF NOT EXISTS idx_bi_user_profiles_role ON bi_user_profiles(bi_role);
CREATE INDEX IF NOT EXISTS idx_bi_user_profiles_dept ON bi_user_profiles(department_id) WHERE department_id IS NOT NULL;

-- Customers master
CREATE TABLE IF NOT EXISTS bi_customers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_code       TEXT UNIQUE,                    -- Nullable until confirmed
    name                TEXT NOT NULL,
    aliases             JSONB NOT NULL DEFAULT '[]',    -- Array of alias strings
    status              TEXT NOT NULL DEFAULT 'ACTIVE',
    source_reference    TEXT,                           -- e.g. ERP ID or import reference
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_customers_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED'))
);

CREATE INDEX IF NOT EXISTS idx_bi_customers_name ON bi_customers(name);
CREATE INDEX IF NOT EXISTS idx_bi_customers_code ON bi_customers(customer_code) WHERE customer_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_customers_aliases ON bi_customers USING gin(aliases);

-- Suppliers master
CREATE TABLE IF NOT EXISTS bi_suppliers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_code       TEXT UNIQUE,
    name                TEXT NOT NULL,
    aliases             JSONB NOT NULL DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'ACTIVE',
    source_reference    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_suppliers_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED'))
);

CREATE INDEX IF NOT EXISTS idx_bi_suppliers_name ON bi_suppliers(name);
CREATE INDEX IF NOT EXISTS idx_bi_suppliers_code ON bi_suppliers(supplier_code) WHERE supplier_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_suppliers_aliases ON bi_suppliers USING gin(aliases);

-- Parts master (links to inventory.item_code via soft reference)
CREATE TABLE IF NOT EXISTS bi_parts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_number         TEXT NOT NULL UNIQUE,           -- Canonical part number
    description         TEXT,
    material_code       TEXT,                           -- Nullable — do not default without approval
    unit_of_measure     TEXT NOT NULL DEFAULT 'EA',
    aliases             JSONB NOT NULL DEFAULT '[]',    -- Array of alias strings
    inventory_item_code TEXT,                           -- Soft ref to inventory.item_code
    is_active           BOOLEAN NOT NULL DEFAULT true,
    source_reference    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_parts_number ON bi_parts(part_number);
CREATE INDEX IF NOT EXISTS idx_bi_parts_aliases ON bi_parts USING gin(aliases);
CREATE INDEX IF NOT EXISTS idx_bi_parts_inventory_code ON bi_parts(inventory_item_code) WHERE inventory_item_code IS NOT NULL;

-- =============================================================================
-- RLS Policies for new tables
-- New tables default to DENY ALL; explicit policies grant required access
-- =============================================================================

ALTER TABLE bi_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_parts ENABLE ROW LEVEL SECURITY;

-- During POC: allow authenticated users to read master data
-- During POC: allow service role to manage all
-- Production: replace with role-specific policies

CREATE POLICY "bi_departments_authenticated_read"
    ON bi_departments FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "bi_departments_service_all"
    ON bi_departments FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "bi_user_profiles_authenticated_read"
    ON bi_user_profiles FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "bi_user_profiles_service_all"
    ON bi_user_profiles FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "bi_customers_authenticated_read"
    ON bi_customers FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "bi_customers_service_all"
    ON bi_customers FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "bi_suppliers_authenticated_read"
    ON bi_suppliers FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "bi_suppliers_service_all"
    ON bi_suppliers FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);

CREATE POLICY "bi_parts_authenticated_read"
    ON bi_parts FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "bi_parts_service_all"
    ON bi_parts FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);
