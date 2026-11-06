-- Rollback for V004: Orders, MRP, and Imports
DROP TABLE IF EXISTS bi_mrp_records CASCADE;
DROP TABLE IF EXISTS bi_mrp_snapshots CASCADE;
DROP TABLE IF EXISTS bi_purchase_order_lines CASCADE;
DROP TABLE IF EXISTS bi_purchase_order_ext CASCADE;
DROP TABLE IF EXISTS bi_rfq_lines CASCADE;
DROP TABLE IF EXISTS bi_rfqs CASCADE;
DROP TABLE IF EXISTS bi_sales_order_lines CASCADE;
DROP TABLE IF EXISTS bi_sales_orders CASCADE;
DROP TABLE IF EXISTS bi_imports CASCADE;
