-- =============================================================================
-- Migration V004: Balbird Intelligence Orders, MRP, and Imports
-- Created: 2026-11-06
-- Purpose: SO, RFQ, PO extensions, MRP snapshots, import infrastructure
-- Existing tables affected: NONE
-- References: purchase_orders.id (UUID, existing), bi_customers.id,
--             bi_suppliers.id, bi_parts.id, employees.id
-- Rollback: See rollback/R004__rollback.sql
-- =============================================================================

-- Import batches (tracks each file upload/import event)
CREATE TABLE IF NOT EXISTS bi_imports (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_type             TEXT NOT NULL,          -- SO, SO_LINES, MRP, EMPLOYEES, PARTS, CUSTOMERS, SUPPLIERS
    source_file_name        TEXT NOT NULL,
    source_hash             TEXT,                   -- SHA-256 of uploaded file
    schema_mapping_version  TEXT,                   -- Which column mapping config was used
    uploader_employee_id    UUID REFERENCES employees(id),
    started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    staged_at               TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    status                  TEXT NOT NULL DEFAULT 'UPLOADING',
    rows_read               INT,
    rows_staged             INT,
    rows_created            INT,
    rows_updated            INT,
    rows_rejected           INT,
    error_summary           JSONB,                  -- {count, examples: [{row, reason}]}
    confirmed_by_employee_id UUID REFERENCES employees(id),
    confirmed_at            TIMESTAMPTZ,
    CONSTRAINT bi_imports_type_check CHECK (
        import_type IN ('SO','SO_LINES','MRP','EMPLOYEES','PARTS','CUSTOMERS','SUPPLIERS','RFQ','RFQ_LINES')
    ),
    CONSTRAINT bi_imports_status_check CHECK (
        status IN ('UPLOADING','STAGED','VALIDATING','VALIDATION_FAILED',
                   'AWAITING_CONFIRMATION','IMPORTING','COMPLETED','FAILED','ROLLED_BACK')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_imports_type ON bi_imports(import_type);
CREATE INDEX IF NOT EXISTS idx_bi_imports_status ON bi_imports(status);
CREATE INDEX IF NOT EXISTS idx_bi_imports_started ON bi_imports(started_at);

-- Sales orders
CREATE TABLE IF NOT EXISTS bi_sales_orders (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    so_number                   TEXT NOT NULL UNIQUE,
    customer_id                 UUID REFERENCES bi_customers(id),
    source_customer_name        TEXT,               -- Original value from source
    order_date                  DATE,
    requested_delivery_date     DATE,
    confirmed_delivery_date     DATE,
    status                      TEXT NOT NULL DEFAULT 'OPEN',
    source_import_id            UUID REFERENCES bi_imports(id),
    source_row_reference        TEXT,               -- e.g. "Sheet1!A42"
    last_source_updated_at      TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_so_status_check CHECK (
        status IN ('DRAFT','OPEN','IN_PROGRESS','COMPLETED','CANCELLED','ON_HOLD')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_so_number ON bi_sales_orders(so_number);
CREATE INDEX IF NOT EXISTS idx_bi_so_customer ON bi_sales_orders(customer_id) WHERE customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_so_status ON bi_sales_orders(status);
CREATE INDEX IF NOT EXISTS idx_bi_so_delivery ON bi_sales_orders(requested_delivery_date) WHERE requested_delivery_date IS NOT NULL;

-- Sales order lines
CREATE TABLE IF NOT EXISTS bi_sales_order_lines (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sales_order_id          UUID NOT NULL REFERENCES bi_sales_orders(id) ON DELETE CASCADE,
    line_number             INT NOT NULL,
    part_id                 UUID REFERENCES bi_parts(id),  -- Nullable if unresolved
    source_part_number      TEXT,                           -- Original value from source
    description             TEXT,
    ordered_quantity        NUMERIC(18,6),
    delivered_quantity      NUMERIC(18,6) NOT NULL DEFAULT 0,
    balance_quantity        NUMERIC(18,6),                  -- Source-derived or computed
    unit_of_measure         TEXT,
    delivery_date           DATE,
    status                  TEXT NOT NULL DEFAULT 'OPEN',
    source_row_reference    TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_sol_unique UNIQUE (sales_order_id, line_number),
    CONSTRAINT bi_sol_status_check CHECK (
        status IN ('OPEN','PARTIAL','COMPLETED','CANCELLED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_sol_order ON bi_sales_order_lines(sales_order_id);
CREATE INDEX IF NOT EXISTS idx_bi_sol_part ON bi_sales_order_lines(part_id) WHERE part_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_sol_part_number ON bi_sales_order_lines(source_part_number) WHERE source_part_number IS NOT NULL;

-- RFQs
CREATE TABLE IF NOT EXISTS bi_rfqs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_number          TEXT NOT NULL UNIQUE,
    customer_id         UUID REFERENCES bi_customers(id),
    source_customer_name TEXT,
    received_at         TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'OPEN',
    source_reference    TEXT,
    source_import_id    UUID REFERENCES bi_imports(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_rfq_status_check CHECK (
        status IN ('OPEN','IN_REVIEW','QUOTED','LOST','CANCELLED','CONVERTED_TO_ORDER')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_rfq_number ON bi_rfqs(rfq_number);
CREATE INDEX IF NOT EXISTS idx_bi_rfq_customer ON bi_rfqs(customer_id) WHERE customer_id IS NOT NULL;

-- RFQ lines (supports 1000+ per RFQ)
CREATE TABLE IF NOT EXISTS bi_rfq_lines (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id                  UUID NOT NULL REFERENCES bi_rfqs(id) ON DELETE CASCADE,
    line_number             INT NOT NULL,
    part_id                 UUID REFERENCES bi_parts(id),
    source_part_number      TEXT,
    description             TEXT,
    quantity                NUMERIC(18,6),
    unit_of_measure         TEXT,
    required_date           DATE,
    technical_status        TEXT NOT NULL DEFAULT 'PENDING',
    source_row_reference    TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_rfql_unique UNIQUE (rfq_id, line_number),
    CONSTRAINT bi_rfql_tech_status_check CHECK (
        technical_status IN ('PENDING','CLARIFICATION_REQUIRED','FEASIBLE','NOT_FEASIBLE','QUOTED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_rfql_rfq ON bi_rfq_lines(rfq_id);
CREATE INDEX IF NOT EXISTS idx_bi_rfql_part ON bi_rfq_lines(part_id) WHERE part_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_rfql_part_number ON bi_rfq_lines(source_part_number) WHERE source_part_number IS NOT NULL;

-- Purchase order extension (enriches existing purchase_orders without modifying it)
CREATE TABLE IF NOT EXISTS bi_purchase_order_ext (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    existing_po_id          UUID REFERENCES purchase_orders(id),  -- Link to existing table (optional)
    po_number               TEXT NOT NULL UNIQUE,                   -- Canonical PO number
    supplier_id             UUID REFERENCES bi_suppliers(id),
    source_supplier_name    TEXT,
    status                  TEXT NOT NULL DEFAULT 'OPEN',
    order_date              DATE,
    expected_delivery_date  DATE,
    source_import_id        UUID REFERENCES bi_imports(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_po_ext_status_check CHECK (
        status IN ('DRAFT','OPEN','PARTIAL','COMPLETED','CANCELLED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_po_ext_number ON bi_purchase_order_ext(po_number);
CREATE INDEX IF NOT EXISTS idx_bi_po_ext_supplier ON bi_purchase_order_ext(supplier_id) WHERE supplier_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_po_ext_existing ON bi_purchase_order_ext(existing_po_id) WHERE existing_po_id IS NOT NULL;

-- Purchase order lines
CREATE TABLE IF NOT EXISTS bi_purchase_order_lines (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id       UUID NOT NULL REFERENCES bi_purchase_order_ext(id) ON DELETE CASCADE,
    line_number             INT NOT NULL,
    part_id                 UUID REFERENCES bi_parts(id),
    source_part_number      TEXT,
    ordered_quantity        NUMERIC(18,6),
    received_quantity       NUMERIC(18,6) NOT NULL DEFAULT 0,
    expected_delivery_date  DATE,
    status                  TEXT NOT NULL DEFAULT 'OPEN',
    source_row_reference    TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_pol_unique UNIQUE (purchase_order_id, line_number),
    CONSTRAINT bi_pol_status_check CHECK (
        status IN ('OPEN','PARTIAL','COMPLETED','CANCELLED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_pol_po ON bi_purchase_order_lines(purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_bi_pol_part ON bi_purchase_order_lines(part_id) WHERE part_id IS NOT NULL;

-- MRP snapshots
CREATE TABLE IF NOT EXISTS bi_mrp_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_import_id    UUID REFERENCES bi_imports(id),
    snapshot_at         TIMESTAMPTZ NOT NULL,
    source_file_name    TEXT NOT NULL,
    schema_version      TEXT,
    import_status       TEXT NOT NULL DEFAULT 'PENDING',
    record_count        INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bi_mrp_snapshot_status_check CHECK (
        import_status IN ('PENDING','IMPORTING','COMPLETED','FAILED')
    )
);

CREATE INDEX IF NOT EXISTS idx_bi_mrp_snapshot_at ON bi_mrp_snapshots(snapshot_at);

-- MRP records per snapshot
CREATE TABLE IF NOT EXISTS bi_mrp_records (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mrp_snapshot_id             UUID NOT NULL REFERENCES bi_mrp_snapshots(id) ON DELETE CASCADE,
    part_id                     UUID REFERENCES bi_parts(id),
    source_part_number          TEXT,                   -- Original value from source
    -- Stock fields (source values preserved exactly)
    available_stock             NUMERIC(18,6),
    reserved_stock              NUMERIC(18,6),
    required_quantity           NUMERIC(18,6),
    pending_purchase_quantity   NUMERIC(18,6),
    open_po_quantity            NUMERIC(18,6),
    open_so_quantity            NUMERIC(18,6),
    open_work_order_quantity    NUMERIC(18,6),
    -- Shortage: source-derived or computed; clearly identified
    shortage_quantity_source    NUMERIC(18,6),          -- As-imported from source column
    shortage_quantity_computed  NUMERIC(18,6),          -- System-computed (available - required)
    shortage_method             TEXT,                   -- 'SOURCE' or 'COMPUTED'
    unit_of_measure             TEXT,
    planning_date               DATE,
    source_row_reference        TEXT,                   -- Row/sheet reference in source file
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bi_mrp_snapshot ON bi_mrp_records(mrp_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_bi_mrp_part ON bi_mrp_records(part_id) WHERE part_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bi_mrp_part_number ON bi_mrp_records(source_part_number) WHERE source_part_number IS NOT NULL;

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE bi_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_sales_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_sales_order_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_rfqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_rfq_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_purchase_order_ext ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_purchase_order_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_mrp_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE bi_mrp_records ENABLE ROW LEVEL SECURITY;

-- All authenticated users can read; service role manages all
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'bi_imports','bi_sales_orders','bi_sales_order_lines',
        'bi_rfqs','bi_rfq_lines','bi_purchase_order_ext',
        'bi_purchase_order_lines','bi_mrp_snapshots','bi_mrp_records'
    ] LOOP
        EXECUTE format(
            'CREATE POLICY "%s_auth_read" ON %s FOR SELECT TO authenticated USING (true)',
            tbl, tbl
        );
        EXECUTE format(
            'CREATE POLICY "%s_service_all" ON %s FOR ALL TO service_role USING (true) WITH CHECK (true)',
            tbl, tbl
        );
    END LOOP;
END;
$$;
